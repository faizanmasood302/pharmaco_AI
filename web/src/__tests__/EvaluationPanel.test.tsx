import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import EvaluationPanel from '../components/EvaluationPanel';
import React from 'react';
import { EvaluationResult } from '../lib/types';

const mockResult: EvaluationResult = {
  status: 'success',
  patient_id: 'PGX-001',
  medication: 'Codeine',
  flagged: true,
  risk_level: 'critical',
  risk_summary: 'Extreme metabolic rate detected.',
  pathways: ['CYP2D6'],
  recommended_alternative: 'Morphine',
  alternative_rationale: 'Avoids CYP2D6 metabolism.',
  cpic_note: 'CPIC Level A',
  patient: {
    id: 'PGX-001',
    display_name: 'Maria Chen',
    age: 42,
    sex: 'F',
    indication: 'Pain',
    cyp_profiles: []
  },
  agent_steps: [],
  clinical_narrative: 'High risk of toxicity.',
  clinical_evidence: 'Clinical trials show...',
  evidence_sources: ['source1.md'],
  decision_confidence: 0.95,
  safety_notes: ['Review required'],
  agent_verdict: 'blocked',
  audit_trail: [],
  logic_tree: {},
  override_requirement: { required: true, reason: 'High risk', required_fields: [] },
  next_best_actions: ['Consult specialist']
};

describe('EvaluationPanel', () => {
  it('displays the risk level and medication name', () => {
    render(<EvaluationPanel result={mockResult} onNoteGenerated={() => {}} />);
    expect(screen.getByText((content, element) => {
      return element?.textContent === 'Evaluation Summary: Codeine';
    })).toBeDefined();
    expect(screen.getByText(/CRITICAL/i)).toBeDefined();
    expect(screen.getByText(/High risk of toxicity/i)).toBeDefined();
  });

  it('shows recommended alternative when flagged', () => {
    render(<EvaluationPanel result={mockResult} onNoteGenerated={() => {}} />);
    expect(screen.getByText(/Morphine/i)).toBeDefined();
  });
});
