import { createContext, useContext, useState } from 'react';

const CoreContext = createContext(null);

/**
 * Provides application-wide state (currently just auth user).
 * Wrap the app root with this; modules access it via useCore().
 */
export function CoreProvider({ children }) {
  const [user, setUser] = useState(null);

  return (
    <CoreContext.Provider value={{ user, setUser }}>
      {children}
    </CoreContext.Provider>
  );
}

/** Access core context. Must be called within a CoreProvider. */
export function useCore() {
  const ctx = useContext(CoreContext);
  if (!ctx) throw new Error('useCore must be used within a CoreProvider');
  return ctx;
}
