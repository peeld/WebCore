/**
 * Wraps the Bulma notification element.
 * @param {string} color    - Bulma colour modifier: 'info' | 'success' | 'warning' | 'danger'
 * @param {function} onDismiss - If provided, renders a close button that calls this.
 */
export default function Notification({ color = 'info', onDismiss, children }) {
  return (
    <div className={`notification is-${color}`}>
      {onDismiss && (
        <button className="delete" onClick={onDismiss} aria-label="Dismiss notification" />
      )}
      {children}
    </div>
  );
}
