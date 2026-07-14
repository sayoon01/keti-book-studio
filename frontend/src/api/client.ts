import axios from "axios";

export const apiClient = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export class ApiError extends Error {
  status?: number;
  detail?: string;

  constructor(message: string, status?: number, detail?: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err?.response?.data?.detail;
    const message = typeof detail === "string" ? detail : err.message;
    return Promise.reject(new ApiError(message, err?.response?.status, detail));
  }
);
