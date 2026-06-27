import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@modules/userauth';

export default function PrivateRoute({ children }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return null;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}
