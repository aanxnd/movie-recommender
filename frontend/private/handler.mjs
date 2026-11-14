import targets from './targets.json' with { type: 'json' }
import { createGateway } from './gateway.mjs'

// Copied as api/gateway.mjs with imports rewritten by the private packaging step.
export default createGateway(process.env, targets)
