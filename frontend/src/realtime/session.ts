// One voice call: the browser talks to the OpenAI Realtime API directly over WebRTC. Audio flows
// on a media track; events (transcripts, tool calls) flow on the "oai-events" data channel.
// Our backend only issues the short-lived key and runs the tools.

import { api, ApiError } from '../api'
import { isFunctionCall, type OutputItem, type ServerEvent } from './events'
import { pendingLabel, runTool, type ToolOutcome } from './tools'

const REALTIME_CALLS_URL = 'https://api.openai.com/v1/realtime/calls'

export type CallStatus =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'user-speaking'
  | 'thinking'
  | 'assistant-speaking'

export interface TranscriptEntry {
  id: string
  role: 'user' | 'assistant' | 'tool'
  text: string
  pending: boolean
  failed?: boolean
  durationMs?: number
}

export interface VoiceState {
  status: CallStatus
  error: string | null
  transcript: TranscriptEntry[]
  /** Reply delays in this call: end of the user's speech to the first audio of the reply. */
  latenciesMs: number[]
}

const INITIAL_STATE: VoiceState = { status: 'idle', error: null, transcript: [], latenciesMs: [] }

export class VoiceSession {
  private state: VoiceState = INITIAL_STATE
  private readonly listeners = new Set<() => void>()
  private onMemoryChanged: () => void = () => {}

  private pc: RTCPeerConnection | null = null
  private dc: RTCDataChannel | null = null
  private mic: MediaStream | null = null
  private audio: HTMLAudioElement | null = null

  /** Bumped on every start and stop, so async work from an earlier call is discarded. */
  private generation = 0
  private speechStoppedAt: number | null = null
  private responseActive = false
  private responseQueued = false
  private readonly toolCalls = new Map<string, Promise<ToolOutcome>>()
  private readonly answeredCalls = new Set<string>()

  /** Called after a tool call saves or deletes a fact, so the memory panel can refresh. */
  setMemoryChangedListener(listener: () => void): void {
    this.onMemoryChanged = listener
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  getSnapshot = (): VoiceState => this.state

  async start(): Promise<void> {
    if (this.state.status !== 'idle') return
    const generation = ++this.generation
    const isStale = () => generation !== this.generation
    this.setState({ ...INITIAL_STATE, status: 'connecting' })

    try {
      // Ask for the microphone before minting a key, so a denied prompt costs nothing.
      const mic = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      if (isStale()) return stopTracks(mic)
      this.mic = mic

      const session = await api.createRealtimeSession()
      if (isStale()) return

      const pc = new RTCPeerConnection()
      this.pc = pc
      const audio = new Audio()
      audio.autoplay = true
      this.audio = audio
      pc.ontrack = (event) => {
        audio.srcObject = event.streams[0]
      }
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'failed') this.fail('The connection to the voice service failed.')
      }
      for (const track of mic.getAudioTracks()) pc.addTrack(track, mic)

      const dc = pc.createDataChannel('oai-events')
      this.dc = dc
      dc.onopen = () => this.setStatus('listening')
      dc.onclose = () => {
        if (!isStale()) this.fail('The call ended unexpectedly.')
      }
      dc.onmessage = (message: MessageEvent<string>) => {
        this.handleEvent(JSON.parse(message.data) as ServerEvent)
      }

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      const response = await fetch(REALTIME_CALLS_URL, {
        method: 'POST',
        body: offer.sdp,
        headers: {
          Authorization: `Bearer ${session.client_secret}`,
          'Content-Type': 'application/sdp',
        },
      })
      if (!response.ok) throw new Error(`The voice service refused the call (${response.status}).`)
      const answer = await response.text()
      if (isStale()) return
      await pc.setRemoteDescription({ type: 'answer', sdp: answer })
    } catch (error) {
      if (!isStale()) this.fail(describeStartError(error))
    }
  }

  stop(): void {
    this.generation++
    this.teardown()
    this.setState({ ...this.state, status: 'idle', transcript: settle(this.state.transcript) })
  }

  /** Tell the model mid-call that the user deleted facts from the memory panel. */
  notifyMemoryDeleted(description: string): void {
    this.send({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'system',
        content: [{ type: 'input_text', text: description }],
      },
    })
  }

  private handleEvent(event: ServerEvent): void {
    switch (event.type) {
      case 'session.created':
        this.setStatus('listening')
        break
      case 'input_audio_buffer.speech_started':
        this.speechStoppedAt = null
        this.upsertEntry(event.item_id, 'user', { pending: true })
        this.setStatus('user-speaking')
        break
      case 'input_audio_buffer.speech_stopped':
        this.speechStoppedAt = performance.now()
        this.setStatus('thinking')
        break
      case 'conversation.item.input_audio_transcription.delta':
        this.appendText(event.item_id, 'user', event.delta)
        break
      case 'conversation.item.input_audio_transcription.completed':
        this.upsertEntry(event.item_id, 'user', { text: event.transcript.trim(), pending: false })
        break
      case 'conversation.item.input_audio_transcription.failed':
        this.upsertEntry(event.item_id, 'user', { text: '(not transcribed)', pending: false })
        break
      case 'response.created':
        this.responseActive = true
        break
      case 'response.output_audio_transcript.delta':
        this.appendText(event.item_id, 'assistant', event.delta)
        break
      case 'response.output_audio_transcript.done':
        this.upsertEntry(event.item_id, 'assistant', { text: event.transcript, pending: false })
        break
      case 'response.function_call_arguments.done':
        // Start the tool now rather than at response.done, to save the time the model spends
        // finishing its spoken filler ("Let me check").
        this.startTool(event.call_id, event.name, event.arguments)
        break
      case 'response.done':
        this.responseActive = false
        void this.finishResponse(event.response.output ?? [])
        break
      case 'output_audio_buffer.started':
        if (this.speechStoppedAt !== null) {
          const latency = Math.round(performance.now() - this.speechStoppedAt)
          this.speechStoppedAt = null
          this.setState({ ...this.state, latenciesMs: [...this.state.latenciesMs, latency] })
        }
        this.setStatus('assistant-speaking')
        break
      case 'output_audio_buffer.stopped':
      case 'output_audio_buffer.cleared':
        this.setStatus(this.toolCalls.size > 0 ? 'thinking' : 'listening')
        break
      case 'error':
        console.warn('Realtime error event', event.error)
        this.setState({ ...this.state, error: event.error.message })
        break
    }
  }

  private startTool(callId: string, name: string, rawArguments: string): void {
    if (this.toolCalls.has(callId)) return
    const generation = this.generation
    const entryId = `tool-${callId}`
    const startedAt = performance.now()
    this.upsertEntry(entryId, 'tool', { text: pendingLabel(name, rawArguments), pending: true })

    const outcome = runTool(name, rawArguments).then((result) => {
      if (generation === this.generation) {
        this.upsertEntry(entryId, 'tool', {
          text: result.summary,
          pending: false,
          failed: !result.ok,
          durationMs: Math.round(performance.now() - startedAt),
        })
        if (result.changedMemory) this.onMemoryChanged()
      }
      return result
    })
    this.toolCalls.set(callId, outcome)
  }

  /** After a response ends, return the results of any tool calls it made and ask for a reply. */
  private async finishResponse(output: OutputItem[]): Promise<void> {
    const calls = output
      .filter(isFunctionCall)
      .filter((call) => call.status !== 'incomplete' && !this.answeredCalls.has(call.call_id))

    if (calls.length === 0) {
      if (this.responseQueued) {
        this.responseQueued = false
        this.send({ type: 'response.create' })
      }
      return
    }

    const generation = this.generation
    for (const call of calls) {
      this.answeredCalls.add(call.call_id)
      this.startTool(call.call_id, call.name, call.arguments)
    }
    const results = await Promise.all(calls.map((call) => this.toolCalls.get(call.call_id)))
    if (generation !== this.generation) return

    calls.forEach((call, index) => {
      this.toolCalls.delete(call.call_id)
      this.send({
        type: 'conversation.item.create',
        item: {
          type: 'function_call_output',
          call_id: call.call_id,
          output: results[index]?.output ?? JSON.stringify({ error: 'The tool did not run.' }),
        },
      })
    })
    this.requestResponse()
  }

  /** Ask the model to respond, waiting if a response is already in progress (one at a time). */
  private requestResponse(): void {
    if (this.responseActive) {
      this.responseQueued = true
    } else {
      this.send({ type: 'response.create' })
    }
  }

  private send(event: Record<string, unknown>): void {
    if (this.dc?.readyState === 'open') this.dc.send(JSON.stringify(event))
  }

  private fail(message: string): void {
    this.generation++
    this.teardown()
    this.setState({
      ...this.state,
      status: 'idle',
      error: message,
      transcript: settle(this.state.transcript),
    })
  }

  private teardown(): void {
    if (this.dc) {
      this.dc.onopen = this.dc.onclose = this.dc.onmessage = null
      this.dc.close()
    }
    if (this.pc) {
      this.pc.ontrack = this.pc.onconnectionstatechange = null
      this.pc.close()
    }
    if (this.mic) stopTracks(this.mic)
    if (this.audio) this.audio.srcObject = null
    this.pc = this.dc = this.mic = this.audio = null
    this.speechStoppedAt = null
    this.responseActive = this.responseQueued = false
    this.toolCalls.clear()
    this.answeredCalls.clear()
  }

  private setStatus(status: CallStatus): void {
    if (this.state.status !== status && this.state.status !== 'idle') {
      this.setState({ ...this.state, status })
    }
  }

  private upsertEntry(
    id: string,
    role: TranscriptEntry['role'],
    changes: Partial<Omit<TranscriptEntry, 'id' | 'role'>>,
  ): void {
    const transcript = this.state.transcript
    const index = transcript.findIndex((entry) => entry.id === id)
    const next =
      index === -1
        ? [...transcript, { id, role, text: '', pending: true, ...changes }]
        : transcript.map((entry, i) => (i === index ? { ...entry, ...changes } : entry))
    this.setState({ ...this.state, transcript: next })
  }

  private appendText(id: string, role: TranscriptEntry['role'], delta: string): void {
    const existing = this.state.transcript.find((entry) => entry.id === id)
    this.upsertEntry(id, role, { text: (existing?.text ?? '') + delta })
  }

  private setState(state: VoiceState): void {
    this.state = state
    for (const listener of this.listeners) listener()
  }
}

function settle(transcript: TranscriptEntry[]): TranscriptEntry[] {
  return transcript
    .filter((entry) => !(entry.pending && entry.text === ''))
    .map((entry) => (entry.pending ? { ...entry, pending: false } : entry))
}

function stopTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop()
}

function describeStartError(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError') {
      return 'Microphone access was denied. Allow it in your browser settings and try again.'
    }
    if (error.name === 'NotFoundError') return 'No microphone was found.'
  }
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Could not start the call.'
}
