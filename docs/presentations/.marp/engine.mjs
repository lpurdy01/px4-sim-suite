/**
 * Custom Marp engine with Mermaid diagram support.
 *
 * For source files: renders mermaid blocks via CDN script
 * For processed files (.processed.md): mermaid already converted to SVG images
 */
import { Marp } from '@marp-team/marp-core'

export default (opts) => {
  const marp = new Marp(opts)

  // Override fence renderer for mermaid blocks (for HTML preview of source files)
  const originalFence = marp.markdown.renderer.rules.fence
  marp.markdown.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    if (token.info.trim() === 'mermaid') {
      return `<pre class="mermaid">${marp.markdown.utils.escapeHtml(token.content)}</pre>`
    }
    return originalFence.call(self, tokens, idx, options, env, self)
  }

  // Inject Mermaid from CDN for HTML preview (only if there are mermaid blocks)
  marp.markdown.core.ruler.after('marpit_slide', 'mermaid_init', (state) => {
    if (state.env._mermaidInjected) return
    
    // Check if any mermaid blocks exist
    const hasMermaid = state.tokens.some(t => 
      t.type === 'fence' && t.info.trim() === 'mermaid'
    )
    if (!hasMermaid) return
    
    state.env._mermaidInjected = true

    const injection = `
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: true, theme: 'default' });
</script>`

    const injected = new state.Token('html_block', '', 0)
    injected.content = injection
    state.tokens.push(injected)
  })

  return marp
}
