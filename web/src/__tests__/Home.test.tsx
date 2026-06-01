import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import Home from '../app/page';
import React from 'react';
import type { EvaluationResult } from '../lib/types';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  useSearchParams: () => ({
    get: vi.fn().mockReturnValue(null),
    toString: vi.fn().mockReturnValue(''),
  }),
  usePathname: () => '/',
}));

vi.mock('@/lib/auth-client', () => ({
  authClient: {
    getSession: vi.fn(() => Promise.resolve({ data: { user: { id: 'tester' } } })),
    signOut: vi.fn(),
  },
}));

// Mock Three.js and components that use it to avoid WebGL issues in jsdom
vi.mock('@/components/MetabolicScene', () => ({
  default: () => <div data-testid="metabolic-scene">Mocked Scene</div>
}));

function jsonResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

const pendingEvaluation: EvaluationResult = {
  evaluation_id: 'eval-1',
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
  cpic_level: 'strong',
  patient: {
    id: 'PGX-001',
    display_name: 'Maria Chen',
    age: 42,
    sex: 'F',
    indication: 'Pain',
    cyp_profiles: [],
  },
  agent_steps: [
    {
      agent: 'Challenge',
      status: 'blocked',
      summary: 'Challenge agent kept the recommendation behind a clinician gate.',
    },
    {
      agent: 'HumanGate',
      status: 'pending',
      summary: 'Clinician approval or rejection is required before dispensing.',
    },
  ],
  clinical_narrative: 'High risk of toxicity.',
  clinical_evidence: 'Clinical trials show...',
  evidence_sources: ['source1.md'],
  decision_confidence: 0.95,
  safety_notes: ['Review required'],
  agent_verdict: 'blocked',
  audit_trail: [],
  logic_tree: {},
  override_requirement: { required: true, reason: 'High risk', required_fields: [] },
  human_gate: {
    required: true,
    status: 'pending',
    reason: 'Clinician review required.',
    required_fields: [],
  },
  next_best_actions: ['Consult specialist'],
};

const approvedEvaluation: EvaluationResult = {
  ...pendingEvaluation,
  human_gate: {
    ...pendingEvaluation.human_gate,
    status: 'approved',
    review_notes: 'Benefits documented.',
    reviewed_by: 'tester',
    reviewed_at: '2026-06-01T00:00:00.000Z',
  },
};

describe('Home Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/patients') {
        return jsonResponse({
          patients: [
            { id: 'PGX-001', display_name: 'Maria Chen', indication: 'Pain', phenotype: 'Ultra-Rapid' }
          ]
        });
      }
      if (url === '/api/medications') {
        return jsonResponse({
          medications: [{ name: 'Codeine', enzyme: 'CYP2D6', is_prodrug: true }]
        });
      }
      if (url === '/api/evaluations/PGX-001') {
        return jsonResponse({ evaluations: [] });
      }
      if (url === '/api/evaluate') {
        return jsonResponse(pendingEvaluation);
      }
      if (url === '/api/evaluations/eval-1/decision') {
        return jsonResponse({ evaluation: approvedEvaluation });
      }
      if (url === '/api/clinical-note') {
        return jsonResponse({ note: 'Approved EHR note' });
      }
      if (url === '/api/clinical-reports') {
        return jsonResponse({ report_id: 'report-1', status: 'saved' });
      }
      if (url === '/api/adherence/plans') {
        return jsonResponse({
          plan_id: 'plan-1',
          patient_id: 'PGX-001',
          medication: 'Codeine',
          check_ins: [],
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    }) as typeof fetch;
  });

  it('renders the prescription console by default', async () => {
    await act(async () => {
      render(<Home />);
    });
    // Use getAllByText because it's in the sidebar and the main header
    await waitFor(() => {
      expect(screen.getAllByText(/Prescription Console/i).length).toBeGreaterThan(0);
    });
    await waitFor(() => {
      expect(screen.getByText(/Maria Chen/i)).toBeInTheDocument();
    });
  });

  it('disables evaluation button when medication is empty', async () => {
    await act(async () => {
      render(<Home />);
    });
    const input = await screen.findByPlaceholderText(/Scan drug database/i) as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: '' } });
    });
    
    const button = screen.getByText(/Run Precision Evaluation/i);
    expect(button).toBeDisabled();
  });

  it('enables evaluation button when medication is entered', async () => {
    await act(async () => {
      render(<Home />);
    });
    const input = await screen.findByPlaceholderText(/Scan drug database/i);
    await act(async () => {
      fireEvent.change(input, { target: { value: 'Codeine' } });
    });
    
    const button = screen.getByText(/Run Precision Evaluation/i);
    expect(button).not.toBeDisabled();
  });

  it('runs evaluate, approval, note generation, and adherence unlock flow', async () => {
    await act(async () => {
      render(<Home />);
    });

    const evaluateButton = await screen.findByRole('button', { name: /Run Precision Evaluation/i });
    await act(async () => {
      fireEvent.click(evaluateButton);
    });

    expect(await screen.findByText(/Human Gate/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Awaiting Approval/i })).toBeDisabled();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText(/Optional clinician rationale/i), {
        target: { value: 'Benefits documented.' },
      });
      fireEvent.click(screen.getByRole('button', { name: /Approve/i }));
    });

    const noteButton = await screen.findByRole('button', { name: /EHR Note/i });
    expect(noteButton).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(noteButton);
    });
    expect(await screen.findByText(/Approved EHR note/i)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Adherence Triage/i }));
    });
    expect(await screen.findByText(/Prescription authorized/i)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Enable Monitoring/i }));
    });
    expect((await screen.findAllByText(/Active Surveillance/i)).length).toBeGreaterThan(0);
  });
});
