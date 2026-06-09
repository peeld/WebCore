/**
 * Centred loading indicator using the Bulma loader class.
 * @param {string} size - Optional Bulma size modifier: 'is-small' | 'is-medium' | 'is-large'
 */
export default function LoadingSpinner({ size = 'is-medium' }) {
  return (
    <div className="has-text-centered p-5">
      <span className={`loader ${size}`} role="status" aria-label="Loading" />
    </div>
  );
}
