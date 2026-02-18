import { useState, useEffect, useCallback } from 'react';
import { fetchContextFolders, fetchContextTree, createContextFolder, ContextFolder, ContextTree } from '../utils/api';

export default function useContexts() {
  const [folders, setFolders] = useState<ContextFolder[]>([]);
  const [tree, setTree] = useState<ContextTree[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshTree = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchContextTree();
      setTree(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFolder = useCallback(async (parentPath = '') => {
    try {
      const data = await fetchContextFolders(parentPath);
      setFolders(data);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { refreshTree(); }, [refreshTree]);

  const addFolder = useCallback(async (path: string, description = '') => {
    await createContextFolder(path, description);
    await refreshTree();
  }, [refreshTree]);

  return { folders, tree, loading, error, refreshTree, loadFolder, addFolder };
}
