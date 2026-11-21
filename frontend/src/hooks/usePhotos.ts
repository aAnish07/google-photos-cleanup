import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { client } from "../api/client";
import type { Filters } from "../types";

export function usePhotos(filters: Filters, page: number, perPage: number) {
  return useQuery({
    queryKey: ["photos", filters, page, perPage],
    queryFn: () => client.photos(filters, page, perPage),
    placeholderData: keepPreviousData,
  });
}

export function useStats() {
  return useQuery({ queryKey: ["stats"], queryFn: () => client.stats() });
}
