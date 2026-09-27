import { useState } from "react";
import "./DemoVideo.css";

export function DemoVideo() {
  const [failed, setFailed] = useState(false);

  return (
    <section className="section" id="demo" aria-labelledby="demo-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="demo-title">See it flinch</h2>
          <p>One mistake, the scar it leaves, and the next attempt that never runs.</p>
        </div>
        <figure className="demo">
          <div className="demo-frame">
            {failed ? (
              <div className="demo-missing" role="note">
                <img src="/favicon.svg" alt="" width="72" height="72" />
                <p>The demo video isn’t available right now.</p>
              </div>
            ) : (
              <video
                controls
                preload="metadata"
                playsInline
                poster="/flinch-poster.png"
                src="/flinch-demo.mp4"
                onError={() => setFailed(true)}
                aria-describedby="demo-caption"
              >
                <a href="/flinch-demo.mp4">Download the Flinch demo video</a>
              </video>
            )}
          </div>
          <figcaption id="demo-caption" className="demo-caption">
            A coding agent deletes a database once. Flinch feels it, blocks the same and similar commands from then
            on, asks before never-seen destroyers, remembers what fixed a failing build, and leaves you in charge:
            approve a prompt or forgive a scar. 82 seconds, with sound.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
