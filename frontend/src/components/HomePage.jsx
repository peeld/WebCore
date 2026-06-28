import { moduleHomeSections } from '../modules.js';

export default function HomePage() {
  return (
    <>
      {moduleHomeSections.map((Section, i) => (
        <Section key={i} />
      ))}
    </>
  );
}
