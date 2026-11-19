// Relays the voice model's tool calls to the backend. The backend authenticates each call with
// the session cookie and only touches this user's data, so nothing here is trusted.

import { api, ApiError } from '../api'

export interface ToolOutcome {
  /** JSON string returned to the model as the function_call_output. */
  output: string
  /** Short description for the transcript. */
  summary: string
  ok: boolean
  changedMemory: boolean
}

export async function runTool(name: string, rawArguments: string): Promise<ToolOutcome> {
  let args: Record<string, unknown>
  try {
    args = JSON.parse(rawArguments) as Record<string, unknown>
  } catch {
    return failure('The tool arguments were not valid JSON.')
  }

  try {
    switch (name) {
      case 'remember': {
        const result = await api.remember(args)
        return {
          output: JSON.stringify({ status: result.status, id: result.memory.id }),
          summary: `${result.status === 'updated' ? 'Updated' : 'Saved'}: ${result.memory.content}`,
          ok: true,
          changedMemory: true,
        }
      }
      case 'forget': {
        const result = await api.forget(args)
        return {
          output: JSON.stringify(result),
          summary: result.status === 'forgotten' ? 'Forgot a fact' : 'Nothing to forget',
          ok: true,
          changedMemory: result.status === 'forgotten',
        }
      }
      case 'web_search': {
        const result = await api.webSearch(args)
        return {
          // Source titles let the model attribute ("according to the BBC") without URLs.
          output: JSON.stringify({
            answer: result.answer,
            source_titles: result.sources.map((source) => source.title),
          }),
          summary: `Searched: ${String(args.query ?? '')}`,
          ok: true,
          changedMemory: false,
        }
      }
      default:
        return failure(`Unknown tool: ${name}.`)
    }
  } catch (error) {
    const message = error instanceof ApiError ? error.message : 'The tool request failed.'
    return failure(message)
  }
}

/** What the transcript shows while a tool is still running. */
export function pendingLabel(name: string, rawArguments: string): string {
  if (name === 'remember') return 'Saving to memory…'
  if (name === 'forget') return 'Forgetting…'
  if (name === 'web_search') {
    try {
      const { query } = JSON.parse(rawArguments) as { query?: unknown }
      if (typeof query === 'string') return `Searching: ${query}`
    } catch {
      // Fall through to the generic label.
    }
    return 'Searching the web…'
  }
  return `Running ${name}…`
}

function failure(message: string): ToolOutcome {
  return {
    output: JSON.stringify({ error: message }),
    summary: message,
    ok: false,
    changedMemory: false,
  }
}
