import { useEffect, useState } from "react";
import { Widget } from "./Widget";
import { USING_MOCK } from "./api";
import houseHero from "./assets/house-hero.jpg";
import "./home.css";
import { SonnfeldMark } from "./Logo";

// Sonnfeld: the installer's website (customer view). reo is not a corner chat bubble here: it is the site's one
// call to action, centre stage. Opening reo pulls the hero copy back and slides reo's sheet down from the top.
export function App() {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false); // keep the conversation when reo is closed and reopened

  function openReo() {
    setMounted(true);
    setOpen(true);
  }

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = ""; removeEventListener("keydown", onKey); };
  }, [open]);

  return (
    <div className={`home-page ${open ? "is-reo" : ""}`}>
      <section className="home" aria-label="Sonnfeld">
        <div className="home-bg" style={{ backgroundImage: `url(${houseHero})` }} aria-hidden />
        <div className="home-shade" aria-hidden />

        <header className="home-top">
          <a className="logo" href="#/" aria-label="Sonnfeld home">
            <SonnfeldMark />
            <span>Sonnfeld</span>
          </a>
          <nav className="home-nav pull-back" aria-label="Main">
            <a href="#solar">Solar</a>
            <a href="#storage">Storage</a>
            <a href="#heat">Heat pumps</a>
            <a href="#about">About us</a>
          </nav>
          <a className="home-login pull-back" href="#/installer">Planner login</a>
        </header>

        <div className="home-center pull-back">
          <h1>Clean energy for your home</h1>
          <p className="home-sub">Solar, storage and heat pumps, planned in two minutes and installed by our own team.</p>
          <ReoEntry onOpen={openReo} />
        </div>

        <ul className="home-trust pull-back" aria-label="Why Sonnfeld">
          <li><Check /> Price estimate in 2 minutes</li>
          <li><Check /> Own installation team</li>
          <li><Check /> 4.9 / 5 from 1,400 homes</li>
        </ul>
      </section>

      <main className="home-more">
        <section className="home-services">
          <article id="solar"><h3>Solar</h3><p>Panels sized to your roof and your real consumption, not to a catalogue.</p></article>
          <article id="storage"><h3>Storage</h3><p>A battery only where it pays off. We tell you when it doesn't.</p></article>
          <article id="heat"><h3>Heat pumps</h3><p>Replace gas or oil heating and run it on your own solar power.</p></article>
        </section>
      </main>

      <footer className="home-foot" id="about">
        <span>Sonnfeld GmbH · Munich · demo site</span>
        <span>reo · powered by Reonic</span>
        <a href="#/installer">Planner login</a>
        {USING_MOCK && <span className="mock-badge">mock API</span>}
      </footer>

      {/* reo's sheet slides down from the top; the hero copy above pulls back at the same time. */}
      <div className={`reo-sheet ${open ? "is-open" : ""}`} aria-hidden={!open}>
        <div className="reo-sheet-inner">
          {mounted && <Widget variant="stage" onClose={() => setOpen(false)} />}
        </div>
      </div>
    </div>
  );
}

// Centre-stage entry to reo, where a site would put its main call to action.
// slot: reo's animated avatar is built separately (ReoAvatar / ReoIntro); it replaces <span className="reo-entry-face" />.
function ReoEntry({ onOpen }: { onOpen: () => void }) {
  return (
    <div className="reo-entry">
      <button className="reo-entry-btn" onClick={onOpen} aria-label="Plan your home with reo">
        <span className="reo-entry-face" aria-hidden>reo</span>
        <span className="reo-entry-text">Plan my home with reo</span>
        <span className="reo-entry-arrow" aria-hidden>→</span>
      </button>
      <span className="reo-entry-note">Free · no sign-up · about 2 minutes</span>
    </div>
  );
}

function Check() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden>
      <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
