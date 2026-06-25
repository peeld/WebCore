import { moduleUserSections } from '../modules.js';

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
              <div key={i} className="column is-half">
                <Section />
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
