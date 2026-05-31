import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import Home from '../app/page';
import React from 'react';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  useSearchParams: () => ({
    get: vi.fn().mockReturnValue('PRESCRIPTION'),
    toString: vi.fn().mockReturnValue(''),
  }),
  usePathname: () => '/',
}));

// Mock Three.js and components that use it to avoid WebGL issues in jsdom
vi.mock('../components/MetabolicScene', () => ({
  default: () => <div data-testid="metabolic-scene">Mocked Scene</div>
}));

describe('Home Page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url === '/api/patients') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            patients: [
              { id: 'PGX-001', display_name: 'Maria Chen', indication: 'Pain', phenotype: 'Ultra-Rapid' }
            ]
          }),
        });
      }
      if (url === '/api/medications') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            medications: [{ name: 'Codeine', enzyme: 'CYP2D6', is_prodrug: true }]
          }),
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
  });

  it('renders the prescription console by default', async () => {
    await act(async () => {
      render(<Home />);
    });
    // Use getAllByText because it's in the sidebar and the main header
    expect(screen.getAllByText(/Prescription Console/i).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText(/Maria Chen/i)).toBeInTheDocument();
    });
  });

  it('disables evaluation button when medication is empty', async () => {
    await act(async () => {
      render(<Home />);
    });
    const input = screen.getByPlaceholderText(/Scan drug database/i) as HTMLInputElement;
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
    const input = screen.getByPlaceholderText(/Scan drug database/i);
    await act(async () => {
      fireEvent.change(input, { target: { value: 'Codeine' } });
    });
    
    const button = screen.getByText(/Run Precision Evaluation/i);
    expect(button).not.toBeDisabled();
  });
});
