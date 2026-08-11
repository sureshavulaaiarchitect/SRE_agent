import { useState, useCallback } from 'react'
import { Playbook } from '../types'

interface PlaybookEditorProps {}

const EXAMPLE_PLAYBOOKS = [
  {
    name: 'oom_killed.yaml',
    trigger: 'OOMKilled',
    steps: [
      'collect_full_evidence',
      'check_pattern',
      'analyze_root_cause',
      'scale_deployment'
    ]
  },
  {
    name: 'image_pull_error.yaml',
    trigger: 'ImagePullBackOff',
    steps: [
      'collect_full_evidence',
      'check_image_pull_pattern',
      'retry_image_pull'
    ]
  }
]

export const PlaybookEditor = ({}: PlaybookEditorProps) => {
  const [selectedPlaybook, setSelectedPlaybook] = useState<string>('')
  const [editorContent, setEditorContent] = useState('')
  const [isDirty, setIsDirty] = useState(false)

  const loadPlaybook = useCallback((name: string) => {
    // Mock loading
    setSelectedPlaybook(name)
    setEditorContent(`
name: ${name}
triggers:
  - OOMKilled
sections:
  - type: parallel
    steps:
      - id: collect_evidence
        action: infrastructure.evidence_collector.collect_full_evidence
        timeout: 30
      - id: get_metrics
        action: get_resource_metrics
  - type: conditional
    if: "{{evidence.restart_count > 3}}"
    then:
      - id: scale_up
        action: scale_deployment
        args:
          replicas: 3
        retry: 2
    else:
      - id: investigate
        action: ai.root_cause_engine.analyze
`)
    setIsDirty(false)
  }, [])

  const savePlaybook = () => {
    // Mock save
    setIsDirty(false)
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <h1 className="page-title gradient-text">Playbook Editor</h1>
        <p className="page-subtitle">Visual editor for deterministic incident response runbooks</p>
      </div>

      <div className="grid-xl">
        {/* Playbook Library */}
        <div className="section">
          <div className="section-header">
            <h2 className="section-title">
              <span>LIB</span>
              Playbook Library
            </h2>
            <button className="btn btn-accent btn-sm">+ New Playbook</button>
          </div>
          <div className="playbook-grid">
            {EXAMPLE_PLAYBOOKS.map((pb) => (
              <div 
                key={pb.name}
                className={`playbook-card ${selectedPlaybook === pb.name ? 'active' : ''}`}
                onClick={() => loadPlaybook(pb.name)}
              >
                <div className="playbook-header">
                  <div className="playbook-icon">PB</div>
                  <div>
                    <div className="playbook-name">{pb.name}</div>
                    <div className="playbook-trigger">Trigger: {pb.trigger}</div>
                  </div>
                </div>
                <div className="playbook-steps">
                  {pb.steps.slice(0, 2).map(step => (
                    <div key={step} className="step-tag">{step}</div>
                  ))}
                  {pb.steps.length > 2 && (
                    <div className="step-tag more">+{pb.steps.length - 2} more</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Editor */}
        <div className="section full-width">
          <div className="section-header">
            <h2 className="section-title">
              <span>ED</span>
              Editor
            </h2>
            <div className="editor-controls">
              <button className="btn btn-secondary btn-sm" onClick={() => loadPlaybook(selectedPlaybook)}>
                Reload
              </button>
              <button 
                className={`btn btn-accent btn-sm ${isDirty ? '' : 'btn-disabled'}`}
                onClick={savePlaybook}
                disabled={!isDirty}
              >
                Save Playbook
              </button>
            </div>
          </div>
          
          <div className="editor-container">
            <textarea
              value={editorContent}
              onChange={(e) => {
                setEditorContent(e.target.value)
                setIsDirty(true)
              }}
              className="playbook-editor"
              placeholder="YAML playbook content..."
              rows={25}
            />
          </div>

          {/* Visual Step Flow */}
          <div className="visual-flow">
            <h3>Visual Flow Preview</h3>
            <div className="flow-diagram">
              <div className="flow-node start">Start</div>
              <div className="flow-edge">→</div>
              <div className="flow-node parallel">
                Evidence<br/>Metrics
              </div>
              <div className="flow-edge diamond">if restarts exceed 3?</div>
              <div className="flow-node yes">Scale Up</div>
              <div className="flow-node no">AI Analyze</div>
              <div className="flow-node end">Complete</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

