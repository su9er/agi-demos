/**
 * useNavigation Hook
 *
 * Provides navigation utilities for components within a layout context.
 * Handles canonical path derivation, path matching, and link generation.
 */

import { useLocation, useNavigate } from 'react-router-dom';

import {
  isCanonicalAbsolutePath,
  joinNavigationPaths,
  normalizeNavigationPath,
} from '@/config/navigation';

export interface UseNavigationOptions {
  /**
   * The base path for the current layout (e.g., '/tenant/abc', '/project/123')
   */
  basePath: string;
}

export interface UseNavigationReturn {
  /**
   * Check if a given path is currently active
   * @param path - Relative path from base or a canonical absolute path
   * @param exact - Require exact match (default: false)
   */
  isActive: (path: string, exact?: boolean) => boolean;

  /**
   * Generate a full path by combining base path with a relative path, or pass
   * through canonical absolute paths unchanged.
   * @param path - Relative path from base (can be empty string)
   */
  getLink: (path: string) => string;

  /**
   * React Router navigate function
   */
  navigate: ReturnType<typeof useNavigate>;

  /**
   * Current location from React Router
   */
  location: ReturnType<typeof useLocation>;
}

function resolveNavigationLink(basePath: string, path: string): string {
  if (!path) {
    return normalizeNavigationPath(basePath);
  }

  if (isCanonicalAbsolutePath(path)) {
    return path;
  }

  return joinNavigationPaths(basePath, path);
}

/**
 * Hook for navigation utilities within a layout.
 */
export function useNavigation(basePath: string): UseNavigationReturn {
  const navigate = useNavigate();
  const location = useLocation();

  /**
   * Check if a path is active based on current location.
   */
  const isActive = (path: string, exact = false): boolean => {
    const currentPath = normalizeNavigationPath(location.pathname);
    const targetPath = normalizeNavigationPath(resolveNavigationLink(basePath, path));

    if (exact || path === '') {
      return currentPath === targetPath;
    }

    return currentPath === targetPath || currentPath.startsWith(`${targetPath}/`);
  };

  /**
   * Generate a full path from a relative or canonical path.
   */
  const getLink = (path: string): string => resolveNavigationLink(basePath, path);

  return {
    isActive,
    getLink,
    navigate,
    location,
  };
}
