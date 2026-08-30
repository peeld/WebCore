import { useState, useEffect, useRef } from 'react';
import { moduleUserSections } from '../modules.js';

// Some Section components render null when they have nothing to show (e.g.
// no bookings yet), often only after their own async load finishes — which
// re-renders the Section itself, not this wrapper. A MutationObserver on the
// wrapper catches that DOM change directly instead of relying on our own
// render cycle, and hides the column so it doesn't leave a blank gap.
function SectionColumn({ component: Section }) {
  const ref = useRef(null);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    const el = ref.current;
    const update = () => setEmpty(el.childElementCount === 0);
    update();
    const observer = new MutationObserver(update);
    observer.observe(el, { childList: true });
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className="column is-half is-flex"
      style={empty ? { display: 'none' } : undefined}
    >
      <Section />
    </div>
  );
}

export default function UserPage() {
  const [visible, setVisible] = useState(() =>
    moduleUserSections.map(s => !s.load)
  );

  useEffect(() => {
    moduleUserSections.forEach(({ load }, i) => {
      if (!load) return;
      load()
        .then(result => setVisible(prev => prev.map((v, j) => j === i ? !!result : v)))
        .catch(() => setVisible(prev => prev.map((v, j) => j === i ? false : v)));
    });
  }, []);

  return (
    <section className="section">
      <div className="container">
        <h1 className="title">My Account</h1>
        {moduleUserSections.length === 0 ? (
          <p className="has-text-grey">No modules have registered account sections.</p>
        ) : (
          <div className="columns is-multiline">
            {moduleUserSections.map(({ component: Section }, i) =>
              visible[i] ? <SectionColumn key={i} component={Section} /> : null
            )}
          </div>
        )}
      </div>
    </section>
  );
}
