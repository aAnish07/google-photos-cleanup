import { useQuery } from "@tanstack/react-query";
import { client } from "../api/client";

// Polls scan status every 2s while a scan is running.
export function useScan() {
  return useQuery({
    queryKey: ["scan-status"],
    queryFn: () => client.scanStatus(),
    refetchInterval: (query) =>
      query.state.data?.running ? 2000 : false,
  });
}

export function useAuthStatus() {
  return useQuery({
    queryKey: ["auth-status"],
    queryFn: () => client.authStatus(),
    refetchInterval: (query) =>
      query.state.data?.authenticated ? false : 3000,
  });
}
