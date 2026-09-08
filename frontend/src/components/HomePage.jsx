import { moduleHomeWidgets, siteHomeSections } from '../modules.js';

// A siteHomeSections entry is either a plain component, or a
// { widget: '<module>.<key>', props } reference into a module's homeWidgets
// map — see core/README.md for the site-side homeSections convention.
function resolveSection(entry) {
  if (typeof entry === 'function') return [entry, {}];

  if (entry && typeof entry.widget === 'string') {
    const [moduleName, widgetKey] = entry.widget.split('.');
    const Component = moduleHomeWidgets[moduleName]?.[widgetKey];
    if (!Component) {
      console.warn(`HomePage: unknown home widget "${entry.widget}"`);
      return null;
    }
    return [Component, entry.props ?? {}];
  }

  console.warn('HomePage: invalid homeSections entry', entry);
  return null;
}

export default function HomePage() {
  return (
    <>
      {siteHomeSections.map((entry, i) => {
        const resolved = resolveSection(entry);
        if (!resolved) return null;
        const [Section, props] = resolved;
        return <Section key={i} {...props} />;
      })}
    </>
  );
}
