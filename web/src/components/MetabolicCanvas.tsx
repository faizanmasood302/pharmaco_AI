"use client";

import React, { useRef, useEffect } from "react";

interface MetabolicCanvasProps {
  hasWarning: boolean;
  riskLevel?: 'optimal' | 'elevated' | 'critical';
}

type MetabolicStateKey = 'optimal' | 'elevated' | 'critical';

interface MetabolicState {
  color: [number, number, number];
  pulse: number;
  chaos: number;
  glow: number;
  speed: number;
  label: string;
}

interface GridPoint {
  px: number;
  py: number;
  sc: number;
  z: number;
  b: number;
}

const METABOLIC_STATES: Record<MetabolicStateKey, MetabolicState> = {
  optimal: { color: [0, 107, 94], pulse: 0.015, chaos: 0, glow: 0.3, label: 'METABOLIC STATE: OPTIMAL', speed: 0.4 },
  elevated: { color: [194, 116, 0], pulse: 0.032, chaos: 0.18, glow: 0.4, label: 'METABOLIC STATE: ELEVATED RISK', speed: 0.7 },
  critical: { color: [186, 26, 26], pulse: 0.07, chaos: 0.44, glow: 0.6, label: 'METABOLIC STATE: CRITICAL RISK', speed: 1.3 }
};

function targetKeyForRisk(hasWarning: boolean, riskLevel?: MetabolicStateKey): MetabolicStateKey {
  if (riskLevel === 'critical') return 'critical';
  if (riskLevel === 'elevated') return 'elevated';
  return hasWarning ? 'elevated' : 'optimal';
}

export default function MetabolicCanvas({ hasWarning, riskLevel }: MetabolicCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const displayState = METABOLIC_STATES[targetKeyForRisk(hasWarning, riskLevel)];
  const stateRef = useRef({
    t: 0,
    noise: [] as number[],
    lerpT: 1,
    target: METABOLIC_STATES.optimal,
    colorL: [0, 255, 170] as [number, number, number],
    pulseL: 0.015,
    chaosL: 0,
    glowL: 0.4,
    speedL: 0.4,
  });

  useEffect(() => {
    // Initialize noise
    const LATS = 18, LONS = 28;
    const noise = [];
    for (let i = 0; i < LATS * LONS; i++) noise.push((Math.random() - 0.5) * 2);
    stateRef.current.noise = noise;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;

    const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
    const lerpArr = (a: number[], b: number[], t: number) =>
      a.map((v, i) => lerp(v, b[i], t)) as [number, number, number];

    const project = (x: number, y: number, z: number, cx: number, cy: number): [number, number, number] => {
      const fov = 420, zOff = 600;
      const scale = fov / (fov + z + zOff);
      return [cx + x * scale, cy + y * scale, scale];
    };

    const spherePt = (lat: number, lon: number, rx: number, ry: number, rz: number, time: number, chaos: number): [number, number, number] => {
      const R = 160;
      const phi = (lat / LATS) * Math.PI;
      const theta = (lon / LONS) * Math.PI * 2;
      const ni = (lat % LATS) * LONS + (lon % LONS);
      const n = stateRef.current.noise[ni];
      const distort = chaos > 0 ? n * chaos * (18 + 12 * Math.sin(time * 2.1 + ni * 0.4)) : 0;
      const r = R + distort;
      const x0 = r * Math.sin(phi) * Math.cos(theta);
      const y0 = r * Math.sin(phi) * Math.sin(theta);
      const z0 = r * Math.cos(phi);
      const cx = Math.cos(rx), sx = Math.sin(rx);
      const cy = Math.cos(ry), sy = Math.sin(ry);
      const cz = Math.cos(rz), sz = Math.sin(rz);
      const x1 = x0, y1 = y0 * cx - z0 * sx, z1 = y0 * sx + z0 * cx;
      const x2 = x1 * cy + z1 * sy, y2 = y1, z2 = -x1 * sy + z1 * cy;
      const x3 = x2 * cz - y2 * sz, y3 = x2 * sz + y2 * cz, z3 = z2;
      return [x3, y3, z3];
    };

    const draw = () => {
      const { target, colorL, pulseL, chaosL, glowL, speedL, lerpT } = stateRef.current;
      const W = canvas.width, H = canvas.height;
      const cx = W / 2, cy = H / 2;
      const R = 160;

      stateRef.current.t += 0.012;
      stateRef.current.lerpT = Math.min(1, lerpT + 0.025);
      const ease = stateRef.current.lerpT < 1 ? 1 - (1 - stateRef.current.lerpT) * (1 - stateRef.current.lerpT) * (1 - stateRef.current.lerpT) : 1;

      // Safe check for target
      const activeTarget = target || METABOLIC_STATES.optimal;

      stateRef.current.colorL = lerpArr(colorL, activeTarget.color, ease * 0.08);
      stateRef.current.pulseL = lerp(pulseL, activeTarget.pulse, ease * 0.06);
      stateRef.current.chaosL = lerp(chaosL, activeTarget.chaos, ease * 0.05);
      stateRef.current.glowL = lerp(glowL, activeTarget.glow, ease * 0.06);
      stateRef.current.speedL = lerp(speedL, activeTarget.speed, ease * 0.06);

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#ffffff'; // Use white background
      ctx.fillRect(0, 0, W, H);

      const rx = stateRef.current.t * 0.19 * stateRef.current.speedL, 
            ry = stateRef.current.t * 0.27 * stateRef.current.speedL, 
            rz = stateRef.current.t * 0.11 * stateRef.current.speedL;
      const pulseScale = 1 + stateRef.current.pulseL * Math.sin(stateRef.current.t * 4.5);
      const [r, g, b] = stateRef.current.colorL.map(Math.round);

      const grid: GridPoint[][] = [];
      for (let la = 0; la <= LATS; la++) {
        grid[la] = [];
        for (let lo = 0; lo <= LONS; lo++) {
          const [x, y, z] = spherePt(la, lo, rx, ry, rz, stateRef.current.t, stateRef.current.chaosL * pulseScale * 30);
          const xs = x * pulseScale, ys = y * pulseScale, zs = z * pulseScale;
          const [px, py, sc] = project(xs, ys, zs, cx, cy);
          const brightness = Math.max(0, Math.min(1, (zs / R + 1) / 2));
          grid[la][lo] = { px, py, sc, z: zs, b: brightness };
        }
      }

      // Subtle glow background
      const glowR = 140 + 40 * Math.sin(stateRef.current.t * 3);
      const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowR);
      grd.addColorStop(0, `rgba(${r},${g},${b},${stateRef.current.glowL * 0.12})`);
      grd.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = grd; ctx.beginPath(); ctx.arc(cx, cy, glowR, 0, Math.PI * 2); ctx.fill();

      ctx.lineWidth = 0.8;
      for (let la = 0; la < LATS; la++) {
        for (let lo = 0; lo < LONS; lo++) {
          const p0 = grid[la][lo], p1 = grid[la][lo + 1], p2 = grid[la + 1][lo];
          const avgB = (p0.b + p1.b) / 2;
          const alpha = 0.12 + avgB * 0.65;
          ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
          ctx.beginPath(); ctx.moveTo(p0.px, p0.py); ctx.lineTo(p1.px, p1.py); ctx.stroke();

          const avgB2 = (p0.b + p2.b) / 2;
          const alpha2 = 0.12 + avgB2 * 0.65;
          ctx.strokeStyle = `rgba(${r},${g},${b},${alpha2})`;
          ctx.beginPath(); ctx.moveTo(p0.px, p0.py); ctx.lineTo(p2.px, p2.py); ctx.stroke();
        }
      }

      const nodes: GridPoint[] = [];
      const step = Math.max(2, Math.round(3 - stateRef.current.chaosL * 1.5));
      for (let la = 0; la <= LATS; la += step) {
        for (let lo = 0; lo < LONS; lo += step) {
          nodes.push(grid[la][lo]);
        }
      }
      nodes.sort((a, b) => a.z - b.z);
      nodes.forEach(n => {
        if (n.b < 0.25) return;
        const nr = 2.2 * n.sc * pulseScale * (0.8 + 0.4 * Math.sin(stateRef.current.t * 5 + n.px * 0.05));
        const ng = ctx.createRadialGradient(n.px, n.py, 0, n.px, n.py, nr * 2.5);
        ng.addColorStop(0, `rgba(${r},${g},${b},${0.6 * n.b})`);
        ng.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = ng; ctx.beginPath(); ctx.arc(n.px, n.py, nr * 2.5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = `rgba(${r},${g},${b},${0.85 * n.b})`;
        ctx.beginPath(); ctx.arc(n.px, n.py, nr, 0, Math.PI * 2); ctx.fill();
      });

      if (stateRef.current.chaosL > 0.05) {
        const numSpark = Math.floor(stateRef.current.chaosL * 6);
        for (let s = 0; s < numSpark; s++) {
          const la = Math.floor(Math.random() * LATS);
          const lo = Math.floor(Math.random() * LONS);
          const p = grid[la][lo];
          if (p.b < 0.5) continue;
          const len = 6 + Math.random() * 15;
          const ang = Math.random() * Math.PI * 2;
          const alpha = 0.4 + Math.random() * 0.4;
          ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
          ctx.lineWidth = 0.6 + Math.random();
          ctx.beginPath();
          ctx.moveTo(p.px, p.py);
          ctx.lineTo(p.px + Math.cos(ang) * len, p.py + Math.sin(ang) * len);
          ctx.stroke();
        }
      }

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  useEffect(() => {
    const targetKey = targetKeyForRisk(hasWarning, riskLevel);
    stateRef.current.target = METABOLIC_STATES[targetKey];
    stateRef.current.lerpT = 0;
  }, [hasWarning, riskLevel]);

  return (
    <div className="relative w-full aspect-[680/480] max-h-[480px] overflow-hidden rounded-xl border border-outline-variant/30 bg-white shadow-lg">
      <canvas
        ref={canvasRef}
        width={680}
        height={480}
        className="block w-full h-full"
      />
      <div 
        className="absolute bottom-4 left-1/2 -translate-x-1/2 font-mono text-[10px] tracking-[0.2em] font-bold uppercase pointer-events-none transition-colors duration-500"
        style={{ color: `rgb(${displayState.color.join(',')})` }}
      >
        {displayState.label}
      </div>
    </div>
  );
}
