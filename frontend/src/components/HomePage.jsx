import { moduleHomeSections } from '../modules.js';

export default function HomePage() {
  return (
    <>
      <section className="hero is-primary is-medium">
        <div className="hero-body">
          <div className="container">
            <p className="title">Welcome to WebTemplate</p>
            <p className="subtitle">
              A modular Django + React platform. Drop in modules to add features.
            </p>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="columns is-multiline">
            <div className="column is-one-third">
              <div className="box">
                <h2 className="title is-5">Modular</h2>
                <p className="content">
                  Each feature lives in its own module. Install or remove modules without touching core.
                </p>
              </div>
            </div>
            <div className="column is-one-third">
              <div className="box">
                <h2 className="title is-5">Full-stack</h2>
                <p className="content">
                  Django REST backend and React + Bulma frontend, wired together and ready to extend.
                </p>
              </div>
            </div>
            <div className="column is-one-third">
              <div className="box">
                <h2 className="title is-5">Convention-driven</h2>
                <p className="content">
                  <code>install.py</code> manages symlinks, manifests, migrations, and npm workspaces automatically.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {moduleHomeSections.map((Section, i) => (
        <Section key={i} />
      ))}
    </>
  );
}
