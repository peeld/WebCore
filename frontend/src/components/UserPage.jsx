import { useState } from 'react';
import { moduleUserSections } from '../modules.js';

function SectionColumn({ Section }) {
  const [visible, setVisible] = useState(true);
  if (!visible) return null;
  return (
    <div className="column is-half is-flex">
      <Section onEmpty={() => setVisible(false)} />
    </div>
  );
}

export default function UserPage() {
  return (
    <section className="section">
      <div className="container">
        <h1 className="title">My Account</h1>
        {moduleUserSections.length === 0 ? (
          <p className="has-text-grey">No modules have registered account sections.</p>
        ) : (
          <div className="columns is-multiline">
            {moduleUserSections.map((Section, i) => (
                <>
              <SectionColumn key={i} Section={Section} />
              </>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
