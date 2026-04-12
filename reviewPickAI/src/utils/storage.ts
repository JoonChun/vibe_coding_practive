import type { StorageSchema } from '@/types';
import { STORAGE_KEYS } from '@/constants';

type StorageValue = StorageSchema[keyof StorageSchema];

/**
 * chrome.storage.local 타입 안전 래퍼
 */
export const storage = {
  get<K extends keyof StorageSchema>(key: K): Promise<StorageSchema[K] | null> {
    return new Promise((resolve) => {
      chrome.storage.local.get(key as string, (result) => {
        resolve((result[key as string] as StorageSchema[K]) ?? null);
      });
    });
  },

  set<K extends keyof StorageSchema>(
    key: K,
    value: StorageSchema[K],
  ): Promise<void> {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [key]: value }, resolve);
    });
  },

  remove(key: keyof StorageSchema): Promise<void> {
    return new Promise((resolve) => {
      chrome.storage.local.remove(key as string, resolve);
    });
  },

  clear(): Promise<void> {
    return new Promise((resolve) => {
      chrome.storage.local.clear(resolve);
    });
  },
};

// 편의 함수들
export const getAnalysis = () =>
  storage.get(STORAGE_KEYS.CURRENT_ANALYSIS as keyof StorageSchema);

export const setAnalysis = (value: StorageSchema['currentAnalysis']) =>
  storage.set(STORAGE_KEYS.CURRENT_ANALYSIS as keyof StorageSchema, value as StorageValue);

export const getApiKey = () =>
  storage.get(STORAGE_KEYS.GEMINI_API_KEY as keyof StorageSchema);

export const setApiKey = (key: string) =>
  storage.set(STORAGE_KEYS.GEMINI_API_KEY as keyof StorageSchema, key as StorageValue);
