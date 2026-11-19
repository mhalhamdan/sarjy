// The subset of Realtime API server events this app handles. Unknown events are ignored.
// Reference: https://developers.openai.com/api/docs/guides/realtime-conversations

export interface FunctionCallItem {
  type: 'function_call'
  id: string
  call_id: string
  name: string
  arguments: string
  status?: 'completed' | 'incomplete' | 'in_progress'
}

export type OutputItem = FunctionCallItem | { type: 'message' | string; id?: string }

export type ServerEvent =
  | { type: 'session.created' | 'session.updated' }
  | { type: 'input_audio_buffer.speech_started'; item_id: string }
  | { type: 'input_audio_buffer.speech_stopped'; item_id: string }
  | { type: 'conversation.item.input_audio_transcription.delta'; item_id: string; delta: string }
  | {
      type: 'conversation.item.input_audio_transcription.completed'
      item_id: string
      transcript: string
    }
  | { type: 'conversation.item.input_audio_transcription.failed'; item_id: string }
  | { type: 'response.created'; response: { id: string } }
  | { type: 'response.output_audio_transcript.delta'; item_id: string; delta: string }
  | { type: 'response.output_audio_transcript.done'; item_id: string; transcript: string }
  | {
      type: 'response.function_call_arguments.done'
      item_id: string
      call_id: string
      name: string
      arguments: string
    }
  | {
      type: 'response.done'
      response: { id: string; status: string; output?: OutputItem[] }
    }
  // WebRTC-only: when the model's audio actually starts and stops playing for the user.
  | { type: 'output_audio_buffer.started' | 'output_audio_buffer.stopped' }
  | { type: 'output_audio_buffer.cleared' }
  | { type: 'error'; error: { type?: string; code?: string; message: string } }

export function isFunctionCall(item: OutputItem): item is FunctionCallItem {
  return item.type === 'function_call'
}
