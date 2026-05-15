import axios from "axios";
import { getToken } from "./auth";

function getApiBase() {
  if (typeof window !== "undefined") {
    // If running on a different port than 8001, it's dev mode — point to backend directly
    const port = window.location.port;
    if (port && port !== "8001") {
      return "http://127.0.0.1:8001/api";
    }
    return window.location.origin + "/api";
  }
  return "/api";
}

const api = axios.create({ baseURL: "/api", timeout: 600000 });

// Override baseURL at request time
api.interceptors.request.use((config) => {
  config.baseURL = getApiBase();
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("auth_token");
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

export interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  book_size: string;
  total_sheets: number;
  total_pages: number;
  total_images: number;
  processed_images: number;
  error: string | null;
}

export interface UploadResponse {
  job_id: string;
  message: string;
  book_size: string;
  num_sheets: number;
  total_pages: number;
  total_images: number;
  total_templates: number;
}

export interface PageList {
  total_pages: number;
  pages: { page_num: number; url: string }[];
}

export const BOOK_SIZES = [
  { value: "12x36", label: "12 × 36 inches" },
  { value: "18x24", label: "18 × 24 inches" },
  { value: "18x26", label: "18 × 26 inches" },
];

export async function uploadAlbum(
  bookSize: string,
  numSheets: number,
  images: File[],
  templates: File[],
  onProgress?: (pct: number) => void
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("book_size", bookSize);
  form.append("num_sheets", numSheets.toString());
  images.forEach((f) => form.append("images", f));
  templates.forEach((f) => form.append("templates", f));

  const { data } = await api.post("/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await api.get(`/jobs/${jobId}/status`);
  return data;
}

export async function getPageList(jobId: string): Promise<PageList> {
  const { data } = await api.get(`/jobs/${jobId}/pages`);
  return data;
}

export function getPagePreviewUrl(jobId: string, pageNum: number): string {
  const base = typeof window !== "undefined" ? window.location.origin : "";
  return `${base}/api/jobs/${jobId}/preview/${pageNum}`;
}

export function getDownloadZipUrl(jobId: string): string {
  const base = typeof window !== "undefined" ? window.location.origin : "";
  return `${base}/api/jobs/${jobId}/download`;
}

export function getDownloadPdfUrl(jobId: string): string {
  const base = typeof window !== "undefined" ? window.location.origin : "";
  return `${base}/api/jobs/${jobId}/pdf`;
}


export interface PSDLayer {
  name: string;
  visible: boolean;
  kind: string;
  x: number;
  y: number;
  width: number;
  height: number;
  parent_group?: string | null;
}

export interface PSDGroup {
  name: string;
  total_children: number;
  boxes: number;
  portrait_boxes: number;
  landscape_boxes: number;
  square_boxes: number;
  children: PSDLayer[];
}

export interface PSDAnalysis {
  preview_id: string;
  filename: string;
  width: number;
  height: number;
  layer_count: number;
  layers: PSDLayer[];
  groups: PSDGroup[];
  preview_url: string;
}

export async function analyzePSD(file: File): Promise<PSDAnalysis> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/psd/analyze", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300000,  // 5 minutes for large PSD files
  });
  return data;
}

export function getPSDPreviewUrl(previewId: string): string {
  const token = getToken();
  const base = typeof window !== "undefined"
    ? (window.location.port && window.location.port !== "8001" ? "http://127.0.0.1:8001" : window.location.origin)
    : "";
  return `${base}/api/psd/preview/${previewId}?token=${token}`;
}
