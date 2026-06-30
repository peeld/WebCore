import { useState, useEffect } from 'react';
import { moduleUserSections } from '../modules.js';

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
              visible[i] ? (
                <div key={i} className="column is-half is-flex">
                  <Section />
                </div>
              ) : null
            )}
          </div>
        )}
      </div>
    </section>
  );
}
