"use client";
import { useState, useEffect } from "react";
import axios from "axios";
import { getToken } from "@/services/auth";

const API_BASE = typeof window !== "undefined"
  ? (window.location.port && window.location.port !== "8001" ? "http://127.0.0.1:8001/api" : window.location.origin + "/api")
  : "/api";

interface DateInfo {
  date: string;
  files: number;
  size_mb: number;
}

export default function StoragePanel({ onClose }: { onClose: () => void }) {
  const [dates, setDates] = useState<DateInfo[]>([]);
  const [totalMb, setTotalMb] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchInfo = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API_BASE}/storage/info`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      setDates(data.dates);
      setTotalMb(data.total_mb);
    } catch { }
    setLoading(false);
  };

  useEffect(() => { fetchInfo(); }, []);

  const handleDelete = async (date: string) => {
    if (!confirm(`Delete all files from ${date === "all" ? "ALL dates" : date}?`)) return;
    setDeleting(date);
    try {
      const form = new FormData();
      form.append("date", date);
      await axios.post(`${API_BASE}/storage/delete`, form, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      await fetchInfo();
    } catch { }
    setDeleting(null);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Storage Manager</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-gray-700">{totalMb} MB</p>
          <p className="text-xs text-gray-500">Total storage used</p>
        </div>

        {loading ? (
          <p className="text-center text-gray-500">Loading...</p>
        ) : dates.length === 0 ? (
          <p className="text-center text-gray-500">No files stored</p>
        ) : (
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {dates.map((d) => (
              <div key={d.date} className="flex items-center justify-between p-3 border rounded-lg">
                <div>
                  <p className="text-sm font-medium">{d.date}</p>
                  <p className="text-xs text-gray-500">{d.files} files • {d.size_mb} MB</p>
                </div>
                <button
                  onClick={() => handleDelete(d.date)}
                  disabled={deleting === d.date}
                  className="px-3 py-1 text-xs bg-red-100 text-red-600 rounded hover:bg-red-200 disabled:opacity-50"
                >
                  {deleting === d.date ? "..." : "Delete"}
                </button>
              </div>
            ))}
          </div>
        )}

        {dates.length > 0 && (
          <button
            onClick={() => handleDelete("all")}
            disabled={deleting === "all"}
            className="w-full py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
          >
            {deleting === "all" ? "Deleting..." : "Delete All Files"}
          </button>
        )}
      </div>
    </div>
  );
}
