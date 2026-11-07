import { useState } from "react";
import { Widget } from "./Widget";
import { USING_MOCK } from "./api";

// The installer's website (customer view). reo lives in the widget.
export function App() {
  const [open, setOpen] = useState(false);
  return (
    <div className="site">
      <header className="site-nav">
        <div className="brand">
          <span className="brand-mark" aria-hidden>☀</span> SolarHaus Müller
        </div>
        <nav>
          <a href="#solar">Solar</a>
          <a href="#storage">Storage</a>
          <a href="#heat">Heat pumps</a>
          <a href="#about">About us</a>
        </nav>
        <span className="site-phone">089 123 456 0</span>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Your installer in Munich since 1998</p>
            <h1>Your own power, planned in minutes.</h1>
            <p className="lede">
              Tell reo, our energy advisor, a little about your home. You get a first solar, battery and heat pump design
              with a price estimate straight away. Our planners then check it and send you a binding quote.
            </p>
            <div className="hero-actions">
              <button className="btn-primary" onClick={() => setOpen(true)}>Plan my system with reo</button>
              <span className="hero-note">Free, no sign-up, takes about two minutes</span>
            </div>
          </div>
          <div className="hero-art" aria-hidden>
            <div className="sun" />
            <div className="roof">
              {Array.from({ length: 12 }).map((_, i) => <span key={i} />)}
            </div>
          </div>
        </section>

        <section className="trust" id="about">
          <div><strong>1,400+</strong><span>homes installed</span></div>
          <div><strong>4.9 / 5</strong><span>customer rating</span></div>
          <div><strong>Own team</strong><span>no subcontractors</span></div>
        </section>

        <section className="services">
          <article id="solar"><h3>Solar</h3><p>Panels sized to your roof and your real consumption, not to a catalogue.</p></article>
          <article id="storage"><h3>Storage</h3><p>A battery only where it pays off. We tell you when it doesn't.</p></article>
          <article id="heat"><h3>Heat pumps</h3><p>Replace gas or oil heating and run it on your own solar power.</p></article>
        </section>
      </main>

      <footer className="site-foot">
        SolarHaus Müller GmbH · demo site for the reo hackathon project
        <a className="foot-link" href="#/installer">Planner login</a>
        {USING_MOCK && <span className="mock-badge">mock API</span>}
      </footer>

      {!open && (
        <button className="launcher" onClick={() => setOpen(true)} aria-label="Open reo">
          <span className="launcher-dot" /> Ask reo
        </button>
      )}
      {open && <Widget onClose={() => setOpen(false)} />}
    </div>
  );
}
