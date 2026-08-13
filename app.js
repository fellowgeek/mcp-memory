/* ==========================================================================
   mcp-memory Landing Page Client Logic & Interactivity
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initCopyButtons();
  initClientConfigTabs();
  initInspectionTabs();
});

/**
 * Toast Notification Manager
 */
function showToast(message) {
  const toast = document.getElementById('toastNotification');
  const toastMsg = document.getElementById('toastMessage');
  if (!toast || !toastMsg) return;

  toastMsg.textContent = message;
  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, 2500);
}

/**
 * Copy to Clipboard Helper
 */
function copyToClipboard(text, btnElement) {
  navigator.clipboard.writeText(text).then(() => {
    if (btnElement) {
      btnElement.classList.add('copied');
      const originalText = btnElement.getAttribute('data-original-text') || btnElement.textContent;
      btnElement.setAttribute('data-original-text', originalText);
      btnElement.textContent = 'Copied!';
      
      setTimeout(() => {
        btnElement.classList.remove('copied');
        btnElement.textContent = originalText;
      }, 2000);
    }
    showToast('Copied configuration snippet to clipboard!');
  }).catch(err => {
    console.error('Failed to copy: ', err);
  });
}

/**
 * Initialize Command & Snippet Copy Buttons
 */
function initCopyButtons() {
  document.querySelectorAll('.btn-copy-cmd').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute('data-copy-target');
      if (targetId) {
        const targetElem = document.getElementById(targetId);
        if (targetElem) {
          copyToClipboard(targetElem.textContent.trim(), btn);
        }
      } else {
        const cmdText = btn.getAttribute('data-copy-text');
        if (cmdText) {
          copyToClipboard(cmdText, btn);
        }
      }
    });
  });
}

/**
 * Configuration Snippets Matrix
 */
const CONFIG_SNIPPETS = {
  antigravity: {
    filename: 'mcp_config.json',
    code: `{
  "mcpServers": {
    "memory": {
      "command": "/ABSOLUTE/PATH/TO/mcp-memory/run.sh"
    }
  }
}`
  },
  claude: {
    filename: 'claude_desktop_config.json',
    code: `{
  "mcpServers": {
    "memory": {
      "command": "/ABSOLUTE/PATH/TO/mcp-memory/run.sh"
    }
  }
}`
  },
  cursor: {
    filename: '~/.cursor/mcp.json',
    code: `{
  "mcpServers": {
    "memory": {
      "command": "/ABSOLUTE/PATH/TO/mcp-memory/run.sh"
    }
  }
}`
  },
  windsurf: {
    filename: '~/.codeium/windsurf/mcp_config.json',
    code: `{
  "mcpServers": {
    "memory": {
      "command": "/ABSOLUTE/PATH/TO/mcp-memory/run.sh"
    }
  }
}`
  },
  codex: {
    filename: '~/.codex/config.toml',
    code: `[mcp_servers.memory]
command = "/ABSOLUTE/PATH/TO/mcp-memory/run.sh"`
  },
  cli: {
    filename: 'Terminal / Shell Command',
    code: `# Claude Code CLI
claude mcp add --scope user memory -- /ABSOLUTE/PATH/TO/mcp-memory/run.sh

# Codex CLI
codex mcp add memory -- /ABSOLUTE/PATH/TO/mcp-memory/run.sh`
  }
};

/**
 * Client Setup Matrix Tabs
 */
function initClientConfigTabs() {
  const tabBtns = document.querySelectorAll('.client-tab-btn');
  const filenameElem = document.getElementById('configFilename');
  const codeDisplayElem = document.getElementById('configCodeDisplay');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const clientKey = btn.getAttribute('data-client');
      const snippetData = CONFIG_SNIPPETS[clientKey];

      if (snippetData && filenameElem && codeDisplayElem) {
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        filenameElem.textContent = snippetData.filename;
        codeDisplayElem.textContent = snippetData.code;
      }
    });
  });
}

/**
 * Dual-Layer Inspection Widget Tabs (Sample Memory Switcher)
 */
const SAMPLE_MEMORIES = {
  preferences: {
    md: `---
type: Agent Memory
title: Coding Style & Guidelines
key: user/preferences/coding_style
namespace: default
tags:
  - preferences
  - python
  - style
generated:
  by: mcp-memory/0.1.0
  at: '2026-08-12T18:00:00Z'
created_at: '2026-08-12T18:00:00Z'
updated_at: '2026-08-12T18:00:00Z'
---

User prefers functional programming principles, explicit typing, and concise error messages.`,
    db: `[SQLite FTS5 Query: SELECT key, content, tags FROM memories_fts WHERE memories_fts MATCH 'preferences']

Row 001 (Match Score: 0.98):
--------------------------------------------------
id:         mem_8f93a1b0
key:        user/preferences/coding_style
namespace:  default
tags:       ["preferences", "python", "style"]
latency_ms: 1.42ms`
  },
  architecture: {
    md: `---
type: Agent Memory
title: Database Schema Architecture
key: project/architecture/schema
namespace: default
tags:
  - architecture
  - sqlite
  - schema
generated:
  by: mcp-memory/0.1.0
  at: '2026-08-12T18:05:00Z'
created_at: '2026-08-12T18:05:00Z'
updated_at: '2026-08-12T18:05:00Z'
---

Dual-layer design: SQLite FTS5 table indexing key/tags/content for sub-20ms lookup + automatic OKF v0.2 Markdown file sync to disk.`,
    db: `[SQLite FTS5 Query: SELECT key, content, tags FROM memories_fts WHERE memories_fts MATCH 'architecture']

Row 002 (Match Score: 0.99):
--------------------------------------------------
id:         mem_3c81d2e9
key:        project/architecture/schema
namespace:  default
tags:       ["architecture", "sqlite", "schema"]
latency_ms: 0.88ms`
  }
};

function initInspectionTabs() {
  const tabBtns = document.querySelectorAll('.inspection-tab-btn');
  const mdDisplay = document.getElementById('widgetMdDisplay');
  const dbDisplay = document.getElementById('widgetDbDisplay');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const sampleKey = btn.getAttribute('data-sample');
      const sample = SAMPLE_MEMORIES[sampleKey];

      if (sample && mdDisplay && dbDisplay) {
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        mdDisplay.textContent = sample.md;
        dbDisplay.textContent = sample.db;
      }
    });
  });
}
