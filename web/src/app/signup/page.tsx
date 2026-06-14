"use client";

import { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import Icon from "@/components/Icon";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    
    const { error: authError } = await authClient.signUp.email({
      email,
      password,
      name,
    });

    if (authError) {
      setError(authError.message || "Failed to create account. Please try again.");
      setLoading(false);
    } else {
      router.push("/");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary mb-6 shadow-lg">
            <Icon name="biotech" className="h-8 w-8 text-on-primary" />
          </div>
          <h1 className="text-3xl font-extrabold text-primary tracking-tight mb-2">GenomicLens MD</h1>
          <p className="text-sm font-medium text-on-surface-variant/70 uppercase tracking-widest">Clinical Access Portal</p>
        </div>

        <div className="glass-card p-8 rounded-3xl shadow-xl border border-outline-variant/30 bg-surface/50 backdrop-blur-xl">
          <h2 className="text-xl font-bold text-on-surface mb-6 text-center">Practitioner Registration</h2>
          
          <form onSubmit={handleSignup} className="space-y-5">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-widest text-on-surface-variant/60 mb-2 ml-1">Full Name</label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-outline-variant">
                  <Icon name="person" className="h-5 w-5" />
                </div>
                <input 
                  type="text" 
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input-clinical w-full bg-surface-container-lowest font-sans rounded-xl py-3.5 pl-12 pr-4 border-outline-variant/20 focus:border-primary transition-all shadow-inner" 
                  placeholder="Dr. Jane Smith"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-widest text-on-surface-variant/60 mb-2 ml-1">Clinical Email</label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-outline-variant">
                  <Icon name="mail" className="h-5 w-5" />
                </div>
                <input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-clinical w-full bg-surface-container-lowest font-sans rounded-xl py-3.5 pl-12 pr-4 border-outline-variant/20 focus:border-primary transition-all shadow-inner" 
                  placeholder="name@clinic.com"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-widest text-on-surface-variant/60 mb-2 ml-1">Secure Password</label>
                <div className="relative">
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 text-outline-variant">
                    <Icon name="lock" className="h-5 w-5" />
                  </div>
                  <input 
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-clinical w-full bg-surface-container-lowest font-sans rounded-xl py-3.5 pl-12 pr-12 border-outline-variant/20 focus:border-primary transition-all shadow-inner" 
                    placeholder="••••••••"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-outline-variant hover:text-primary transition-colors"
                  >
                    <Icon name={showPassword ? "visibility_off" : "visibility"} className="h-5 w-5" />
                  </button>
                </div>
            </div>

            {error && (
              <div className="p-4 rounded-xl bg-error/10 border border-error/20 flex items-start gap-3 animate-in fade-in slide-in-from-top-2 duration-200">
                <Icon name="error" className="h-5 w-5 text-error shrink-0 mt-0.5" />
                <p className="text-xs font-medium text-error leading-relaxed">{error}</p>
              </div>
            )}

            <button 
              type="submit" 
              disabled={loading}
              className="w-full bg-primary text-on-primary font-bold uppercase tracking-widest py-4 rounded-xl hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg flex items-center justify-center gap-2 active:scale-[0.98] mt-4"
            >
              {loading ? (
                <>
                  <Icon name="progress_activity" className="h-5 w-5 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Icon name="verified_user" className="h-5 w-5" />
                  Authorize Registration
                </>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-outline-variant/30 text-center">
            <p className="text-xs text-on-surface-variant/70">
              Already authorized?{" "}
              <button 
                onClick={() => router.push("/login")}
                className="font-bold text-primary hover:underline underline-offset-4"
              >
                Access Portal
              </button>
            </p>
          </div>
        </div>
        
        <p className="mt-10 text-[10px] text-center text-on-surface-variant/40 font-medium uppercase tracking-[0.2em] leading-relaxed">
          HIPAA Compliant Session &bull; Pharmacogenomic Precision Harness<br/>
          &copy; 2026 GenomicLens MD Precision Systems
        </p>
      </div>
    </div>
  );
}
