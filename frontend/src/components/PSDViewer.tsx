"use client";
import { useState } from "react";
import Dropzone from "./Dropzone";
import SlotEditor from "./SlotEditor";
import { analyzePSD, getPSDPreviewUrl, PSDAnalysis, PSDLayer } from "@/services/api";
import { getToken } from "@/services/auth";
import axios from "axios";

const API_BASE = "/api";

function getApiBase() {
  if (typeof window !== "undefined") {
    const port = window.location.port;
    if (port && port !== "8001") {
      return "http://127.0.0.1:8001/api";
    }
    return window.location.origin + "/api";
  }
  return "/api";
}

interface PSDSession {
  file: File;
  analysis: PSDAnalysis | null;
  slotPhotos: Record<number, File[]>;
  bulkPhotos: File[];
  resultUrl: string | null;
}

export default function PSDViewer() {
  const [files, setFiles] = useState<File[]>([]);
  const [sessions, setSessions] = useState<PSDSession[]>([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [compositing, setCompositing] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoveredLayer, setHoveredLayer] = useState<PSDLayer | null>(null);
  const [assignMode, setAssignMode] = useState<"bulk" | "individual">("bulk");
  const [editingSlot, setEditingSlot] = useState<{ index: number; photo: File; layer: PSDLayer } | null>(null);
  const [viewMode, setViewMode] = useState<"gallery" | "editor">("gallery");

  const activeSession = sessions[activeIdx] || null;
  const analysis = activeSession?.analysis || null;

  const handleUpload = async () => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    const newSessions: PSDSession[] = [];
    for (let idx = 0; idx < files.length; idx++) {
      const f = files[idx];
      setError(`Analyzing ${idx + 1}/${files.length}: ${f.name}...`);
      try {
        const result = await analyzePSD(f);
        newSessions.push({ file: f, analysis: result, slotPhotos: {}, bulkPhotos: [], resultUrl: null });
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message || "Unknown error";
        newSessions.push({ file: f, analysis: null, slotPhotos: {}, bulkPhotos: [], resultUrl: null });
        setError(`Failed ${f.name}: ${msg}`);
      }
    }
    setSessions(newSessions);
    setActiveIdx(0);
    setLoading(false);
    setError(null);
  };

  const updateSession = (idx: number, updates: Partial<PSDSession>) => {
    setSessions((prev) => prev.map((s, i) => (i === idx ? { ...s, ...updates } : s)));
  };

  const handleBulkPhotos = (photos: File[]) => {
    updateSession(activeIdx, { bulkPhotos: photos, slotPhotos: Object.fromEntries(photos.map((f, i) => [i, [f]])) });
  };

  const handleSlotPhoto = (slotIndex: number, e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(e.target.files || []);
    if (newFiles.length > 0) {
      const current = activeSession?.slotPhotos || {};
      updateSession(activeIdx, { slotPhotos: { ...current, [slotIndex]: newFiles } });
    }
  };

  const handleComposite = async () => {
    if (!analysis || !activeSession) return;
    setCompositing(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("preview_id", analysis.preview_id);
      if (assignMode === "bulk") {
        (activeSession.bulkPhotos || []).forEach((photo, i) => {
          form.append(`slot_${i}`, photo);
        });
      } else {
        let photoIdx = 0;
        Object.values(activeSession.slotPhotos || {}).forEach((files) => {
          files.forEach((photo) => {
            form.append(`slot_${photoIdx}`, photo);
            photoIdx++;
          });
        });
      }
      const { data } = await axios.post(`${getApiBase()}/psd/composite-slots`, form, {
        headers: { "Content-Type": "multipart/form-data", "Authorization": `Bearer ${getToken()}` },
        timeout: 120000,
      });
      updateSession(activeIdx, { resultUrl: `${getApiBase()}/psd/result/${data.result_id}?token=${getToken()}` });
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || "Compositing failed");
    } finally {
      setCompositing(false);
    }
  };

  const reset = () => {
    setFiles([]);
    setSessions([]);
    setActiveIdx(0);
    setError(null);
    setHoveredLayer(null);
  };

  const getSlots = (): PSDLayer[] => {
    if (!analysis) return [];
    const groupNames = new Set((analysis.groups || []).map(g => g.name));
    const groupChildren = analysis.layers.filter(
      l => l.parent_group && l.width > 200 && l.height > 200
        && !(l.width > analysis.width * 0.95 && l.height > analysis.height * 0.95)
        && !l.name.toLowerCase().includes("background")
    );
    if (groupChildren.length > 0) return groupChildren;
    return analysis.layers.filter(
      l => l.width > 200 && l.height > 200
        && !l.name.toLowerCase().includes("background")
        && !groupNames.has(l.name)
        && !(l.width > analysis.width * 0.95 && l.height > analysis.height * 0.95)
    );
  };

  const slots = getSlots();
  const slotPhotos = activeSession?.slotPhotos || {};
  const assignedCount = Object.values(slotPhotos).reduce((sum, files) => sum + files.length, 0);
  const resultUrl = activeSession?.resultUrl || null;

  return (
    <div className="space-y-6">
      {/* Slot Editor Modal */}
      {editingSlot && resultUrl && (
        <SlotEditor
          resultId={resultUrl.split("?")[0].split("/").pop()!}
          slotIndex={editingSlot.index}
          slotWidth={editingSlot.layer.width}
          slotHeight={editingSlot.layer.height}
          photo={editingSlot.photo}
          onDone={(newResultId) => {
            // Update the result URL to force refresh
            updateSession(activeIdx, { resultUrl: `${getApiBase()}/psd/result/${newResultId}?token=${getToken()}&t=${Date.now()}` });
            setEditingSlot(null);
          }}
          onCancel={() => setEditingSlot(null)}
        />
      )}

      {/* Download loader overlay */}
      {downloading && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-8 text-center space-y-4 shadow-xl">
            <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-lg font-medium">Downloading files...</p>
            <p className="text-sm text-gray-500">Saving {sessions.filter(s => s.resultUrl).length} pages as numbered JPEGs</p>
          </div>
        </div>
      )}

      {sessions.length === 0 ? (
        <>
          <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
            <h2 className="text-lg font-semibold">PSD File Viewer & Editor</h2>
            <p className="text-sm text-gray-500">
              Upload one or more PSD files to view layers and place photos into slots.
            </p>
            <Dropzone
              label="PSD Files"
              accept={{ "application/octet-stream": [".psd"], "image/vnd.adobe.photoshop": [".psd"] }}
              files={files}
              onFiles={setFiles}
              maxFiles={50}
              hint="Upload one or multiple PSD files"
            />
          </div>
          {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">{error}</div>}
          <button
            onClick={handleUpload}
            disabled={!files.length || loading}
            className="w-full py-3 px-6 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? `⏳ Analyzing... (large files may take 1-2 min each)` : `Analyze ${files.length} PSD file${files.length > 1 ? "s" : ""}`}
          </button>
        </>
      ) : (
        <>
          {/* View mode toggle */}
          <div className="flex items-center justify-between">
            <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
              <button
                onClick={() => setViewMode("gallery")}
                className={`px-4 py-1.5 rounded-md text-sm font-medium ${viewMode === "gallery" ? "bg-white shadow" : "text-gray-500"}`}
              >
                🖼 Overview
              </button>
              <button
                onClick={() => setViewMode("editor")}
                className={`px-4 py-1.5 rounded-md text-sm font-medium ${viewMode === "editor" ? "bg-white shadow" : "text-gray-500"}`}
              >
                ✏️ Editor
              </button>
            </div>
            <button onClick={reset} className="px-3 py-1 text-xs text-red-500 hover:bg-red-50 rounded">Reset All</button>
          </div>

          {/* Add More PSD Files */}
          <div className="bg-white rounded-xl shadow-sm border p-3">
            <div className="flex items-center gap-3">
              <label className="flex-1 cursor-pointer">
                <input
                  type="file"
                  accept=".psd"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const newFiles = Array.from(e.target.files || []);
                    if (!newFiles.length) return;
                    setLoading(true);
                    setError(null);
                    const newSessions: PSDSession[] = [];
                    for (const f of newFiles) {
                      try {
                        const result = await analyzePSD(f);
                        newSessions.push({ file: f, analysis: result, slotPhotos: {}, bulkPhotos: [], resultUrl: null });
                      } catch (err: any) {
                        newSessions.push({ file: f, analysis: null, slotPhotos: {}, bulkPhotos: [], resultUrl: null });
                      }
                    }
                    setSessions(prev => [...prev, ...newSessions]);
                    setLoading(false);
                    e.target.value = "";
                  }}
                />
                <span className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium text-gray-700 inline-block cursor-pointer">
                  {loading ? "⏳ Analyzing..." : "+ Add More PSD Files"}
                </span>
              </label>
              <span className="text-xs text-gray-400">{sessions.length} files loaded</span>
            </div>
          </div>

          {/* Gallery View */}
          {viewMode === "gallery" && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h2 className="text-lg font-semibold">All PSD Files ({sessions.length})</h2>
                <div className="text-sm text-gray-500">
                  {sessions.filter(s => s.resultUrl).length}/{sessions.length} completed
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {sessions.map((s, i) => {
                  const a = s.analysis;
                  const slotsForThis = a ? a.layers.filter(
                    l => l.parent_group && l.width > 200 && l.height > 200 && !(l.width > a.width * 0.95 && l.height > a.height * 0.95) && !l.name.toLowerCase().includes("background")
                  ) : [];
                  const fallbackSlots = a ? a.layers.filter(
                    l => l.width > 200 && l.height > 200 && !l.name.toLowerCase().includes("background") && !(l.width > a.width * 0.95 && l.height > a.height * 0.95)
                  ) : [];
                  const displaySlots = slotsForThis.length > 0 ? slotsForThis : fallbackSlots;
                  const portrait = displaySlots.filter(l => l.height > l.width * 1.2).length;
                  const landscape = displaySlots.filter(l => l.width > l.height * 1.2).length;
                  const square = displaySlots.length - portrait - landscape;

                  return (
                    <div
                      key={i}
                      onClick={() => { setActiveIdx(i); setViewMode("editor"); }}
                      className={`bg-white rounded-lg border overflow-hidden cursor-pointer hover:shadow-md transition-shadow ${
                        s.resultUrl ? "border-green-300" : "border-gray-200"
                      }`}
                    >
                      {/* Thumbnail */}
                      <div className="aspect-video bg-gray-100 relative overflow-hidden">
                        {a && (
                          <img
                            src={s.resultUrl || getPSDPreviewUrl(a.preview_id)}
                            alt={s.file.name}
                            className="w-full h-full object-contain"
                          />
                        )}
                        {s.resultUrl && (
                          <div className="absolute top-1 right-1 bg-green-500 text-white text-xs px-1.5 py-0.5 rounded">✓</div>
                        )}
                        <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs px-2 py-1">
                          {i + 1}. {s.file.name}
                        </div>
                      </div>
                      {/* Info */}
                      <div className="p-2">
                        {a ? (
                          <div className="flex gap-1 flex-wrap">
                            <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">{displaySlots.length} slots</span>
                            {portrait > 0 && <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">{portrait}↕</span>}
                            {landscape > 0 && <span className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">{landscape}↔</span>}
                            {square > 0 && <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">{square}◻</span>}
                          </div>
                        ) : (
                          <span className="text-xs text-red-500">Failed</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Editor View */}
          {viewMode === "editor" && (
          <>
          {/* File tabs */}
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="flex border-b overflow-x-auto">
              {sessions.map((s, i) => (
                <div key={i} className="flex items-center border-r">
                  <button
                    onClick={() => { setActiveIdx(i); setHoveredLayer(null); }}
                    className={`px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
                      i === activeIdx ? "bg-primary-600 text-white" : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    {i + 1}. {s.file.name}
                    {s.resultUrl && " ✓"}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const newSessions = sessions.filter((_, idx) => idx !== i);
                      setSessions(newSessions);
                      if (activeIdx >= newSessions.length) setActiveIdx(Math.max(0, newSessions.length - 1));
                    }}
                    className={`px-2 py-2 text-xs hover:bg-red-100 hover:text-red-600 ${
                      i === activeIdx ? "text-white/70 hover:text-red-600 hover:bg-red-100" : "text-gray-400"
                    }`}
                    title="Remove this file"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <div className="ml-auto flex items-center gap-2 px-2">
                {sessions.some(s => s.resultUrl) && (
                  <>
                    <button
                      disabled={downloading}
                      onClick={async () => {
                        setDownloading(true);
                        setError(null);
                        try {
                          const results = sessions.filter(s => s.resultUrl);
                          for (let i = 0; i < results.length; i++) {
                            const resp = await axios.get(results[i].resultUrl!, { responseType: "blob", timeout: 120000, headers: { "Authorization": `Bearer ${getToken()}` } });
                            const url = window.URL.createObjectURL(new Blob([resp.data]));
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = `${String(i + 1).padStart(3, "0")}.jpg`;
                            a.click();
                            window.URL.revokeObjectURL(url);
                            await new Promise(r => setTimeout(r, 500));
                          }
                        } catch { setError("Download failed"); }
                        finally { setDownloading(false); }
                      }}
                      className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                    >
                      {downloading ? "⏳..." : `⬇ JPEG (${sessions.filter(s => s.resultUrl).length})`}
                    </button>
                    <button
                      disabled={downloading}
                      onClick={async () => {
                        setDownloading(true);
                        setError(null);
                        try {
                          const results = sessions.filter(s => s.resultUrl);
                          for (let i = 0; i < results.length; i++) {
                            const rid = results[i].resultUrl!.split("?")[0].split("/").pop()!;
                            const resp = await axios.get(`${getApiBase()}/psd/result-psd/${rid}`, {
                              responseType: "blob", timeout: 120000,
                              headers: { "Authorization": `Bearer ${getToken()}` },
                            });
                            const url = window.URL.createObjectURL(new Blob([resp.data]));
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = `${String(i + 1).padStart(3, "0")}.psd`;
                            a.click();
                            window.URL.revokeObjectURL(url);
                            await new Promise(r => setTimeout(r, 500));
                          }
                        } catch { setError("PSD download failed"); }
                        finally { setDownloading(false); }
                      }}
                      className="px-3 py-1 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
                    >
                      {downloading ? "⏳..." : `⬇ PSD (${sessions.filter(s => s.resultUrl).length})`}
                    </button>
                    <button
                      disabled={downloading}
                      onClick={async () => {
                        setDownloading(true);
                        setError(null);
                        try {
                          const resultIds = sessions.filter(s => s.resultUrl).map(s => s.resultUrl!.split("?")[0].split("/").pop()!).join(",");
                          const form = new FormData();
                          form.append("result_ids", resultIds);
                          const resp = await axios.post(`${getApiBase()}/psd/download-all-pdf`, form, {
                            responseType: "blob", timeout: 120000,
                            headers: { "Authorization": `Bearer ${getToken()}` },
                          });
                          const url = window.URL.createObjectURL(new Blob([resp.data]));
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = "album.pdf";
                          a.click();
                          window.URL.revokeObjectURL(url);
                        } catch { setError("PDF download failed"); }
                        finally { setDownloading(false); }
                      }}
                      className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                    >
                      {downloading ? "⏳..." : "⬇ PDF"}
                    </button>
                  </>
                )}
                <button onClick={reset} className="px-3 py-1 text-xs text-red-500 hover:bg-red-50 rounded">
                  Reset All
                </button>
              </div>
            </div>
            {sessions.length === 0 && (
              <div className="p-4 text-center text-gray-500">All files removed. <button onClick={reset} className="underline">Start over</button></div>
            )}
            {!analysis && activeSession && (
              <div className="p-4 text-center text-gray-500">Failed to analyze this file</div>
            )}
          </div>

          {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">{error}</div>}

          {analysis && (
            <>
              {/* Header */}
              <div className="bg-white rounded-xl shadow-sm border p-4 flex justify-between items-center">
                <div>
                  <h2 className="text-lg font-semibold">{analysis.filename}</h2>
                  <p className="text-sm text-gray-500">
                    {analysis.width} × {analysis.height} px | {slots.length} photo slots
                  </p>
                </div>
                <span className="text-sm text-gray-400">File {activeIdx + 1} of {sessions.length}</span>
              </div>

              {/* Slot Summary */}
              <div className="bg-white rounded-xl shadow-sm border p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Detected Slots</h3>
                <div className="grid grid-cols-4 gap-3 text-center">
                  <div className="bg-blue-50 rounded-lg p-3">
                    <p className="text-2xl font-bold text-blue-600">{slots.length}</p>
                    <p className="text-xs text-blue-500">Total</p>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-3">
                    <p className="text-2xl font-bold text-purple-600">{slots.filter(l => l.height > l.width * 1.2).length}</p>
                    <p className="text-xs text-purple-500">↕ Portrait</p>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-3">
                    <p className="text-2xl font-bold text-orange-600">{slots.filter(l => l.width > l.height * 1.2).length}</p>
                    <p className="text-xs text-orange-500">↔ Landscape</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3">
                    <p className="text-2xl font-bold text-green-600">{slots.filter(l => !(l.height > l.width * 1.2) && !(l.width > l.height * 1.2)).length}</p>
                    <p className="text-xs text-green-500">◻ Square</p>
                  </div>
                </div>
              </div>

              {/* Photo Assignment */}
              <div className="bg-white rounded-xl shadow-sm border p-4">
                <div className="flex gap-2 mb-4">
                  <button
                    onClick={() => setAssignMode("bulk")}
                    className={`px-4 py-2 rounded-lg text-sm font-medium ${
                      assignMode === "bulk" ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    📦 Bulk Upload
                  </button>
                  <button
                    onClick={() => setAssignMode("individual")}
                    className={`px-4 py-2 rounded-lg text-sm font-medium ${
                      assignMode === "individual" ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    🎯 Individual
                  </button>
                </div>

                {assignMode === "bulk" ? (
                  <Dropzone
                    label={`Drop photos here (auto-assigned to ${slots.length} slots by orientation)`}
                    accept={{ "image/*": [".jpg", ".jpeg", ".png", ".webp"] }}
                    files={activeSession?.bulkPhotos || []}
                    onFiles={handleBulkPhotos}
                    maxFiles={50}
                    hint="Portrait photos → vertical boxes, landscape → horizontal boxes"
                  />
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {slots.map((layer, i) => (
                      <div
                        key={i}
                        onMouseEnter={() => setHoveredLayer(layer)}
                        onMouseLeave={() => setHoveredLayer(null)}
                        className={`p-3 border rounded-lg ${
                          hoveredLayer?.name === layer.name ? "border-red-300 bg-red-50" : "border-gray-200"
                        }`}
                      >
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-sm font-medium">Slot {i + 1}</span>
                          <span className="text-xs text-gray-400">
                            {layer.width > layer.height * 1.2 ? "↔" : layer.height > layer.width * 1.2 ? "↕" : "◻"}
                            {" "}{layer.width}×{layer.height}
                          </span>
                        </div>
                        <input type="file" accept="image/*" multiple onChange={(e) => handleSlotPhoto(i, e)} className="w-full text-xs" />
                        {slotPhotos[i] && slotPhotos[i].length > 0 && (
                          <div className="mt-1">
                            {slotPhotos[i].map((f, fi) => (
                              <p key={fi} className="text-xs text-green-600">✓ {f.name}</p>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Preview */}
              <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
                <div className="p-3 border-b bg-gray-50 text-sm font-medium text-gray-600">
                  {resultUrl ? "✅ Result (click a slot to adjust)" : "Preview"}
                </div>
                <div className="p-4">
                  <div className="relative inline-block w-full">
                    <img
                      src={resultUrl || getPSDPreviewUrl(analysis.preview_id)}
                      alt="Preview"
                      className="w-full h-auto rounded"
                    />
                    {!resultUrl && slots.map((layer, i) => (
                      <div
                        key={i}
                        onMouseEnter={() => setHoveredLayer(layer)}
                        onMouseLeave={() => setHoveredLayer(null)}
                        className={`absolute border-2 transition-colors ${
                          hoveredLayer?.name === layer.name ? "border-red-500 bg-red-500/20"
                            : slotPhotos[i]?.length ? "border-green-500 bg-green-500/10"
                            : "border-blue-400 bg-blue-400/10"
                        }`}
                        style={{
                          left: `${(layer.x / analysis.width) * 100}%`,
                          top: `${(layer.y / analysis.height) * 100}%`,
                          width: `${(layer.width / analysis.width) * 100}%`,
                          height: `${(layer.height / analysis.height) * 100}%`,
                        }}
                      >
                        <span className="absolute -top-5 left-0 text-xs bg-blue-500 text-white px-1 rounded">{i + 1}</span>
                      </div>
                    ))}
                    {/* Clickable slots on result for adjustment */}
                    {resultUrl && slots.map((layer, i) => (
                      <div
                        key={`adj-${i}`}
                        onClick={() => {
                          const photo = slotPhotos[i]?.[0];
                          if (photo) {
                            setEditingSlot({ index: i, photo, layer });
                          }
                        }}
                        className="absolute border-2 border-transparent hover:border-yellow-400 hover:bg-yellow-400/10 cursor-pointer transition-colors"
                        style={{
                          left: `${(layer.x / analysis.width) * 100}%`,
                          top: `${(layer.y / analysis.height) * 100}%`,
                          width: `${(layer.width / analysis.width) * 100}%`,
                          height: `${(layer.height / analysis.height) * 100}%`,
                        }}
                        title={`Click to adjust Slot ${i + 1}`}
                      >
                        <span className="absolute top-1 right-1 text-xs bg-yellow-500 text-white px-1 rounded opacity-0 hover:opacity-100 transition-opacity">✏️</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-4">
                <button
                  onClick={handleComposite}
                  disabled={assignedCount === 0 || compositing}
                  className="flex-1 py-3 px-6 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {compositing ? "Placing..." : `Place ${assignedCount} Photos`}
                </button>
                {resultUrl && (
                  <a href={resultUrl} download={`${String(activeIdx + 1).padStart(3, '0')}_${analysis.filename.replace('.psd', '')}.jpg`}
                    className="py-3 px-6 border border-gray-300 rounded-lg font-medium hover:bg-gray-50 text-center">
                    ⬇ Download ({activeIdx + 1})
                  </a>
                )}
                {resultUrl && (
                  <button
                    onClick={async () => {
                      const photos = activeSession?.bulkPhotos || [];
                      const slotPhotoFiles = Object.values(activeSession?.slotPhotos || {}).flat();
                      const allPhotos = photos.length > 0 ? photos : slotPhotoFiles;
                      if (allPhotos.length === 0) { alert("No photos to move"); return; }

                      // Ask for source folder (remembers last used)
                      let sourceFolder = localStorage.getItem("photo_source_folder") || "";
                      if (!sourceFolder) {
                        sourceFolder = prompt("Where are your photos located?\nEnter folder path (e.g., D:\\MyPhotos):") || "";
                        if (!sourceFolder) return;
                        localStorage.setItem("photo_source_folder", sourceFolder);
                      }

                      const filenames = allPhotos.map(f => f.name).join(",");
                      try {
                        const form = new FormData();
                        form.append("filenames", filenames);
                        form.append("source_folder", sourceFolder);
                        const { data } = await axios.post(`${getApiBase()}/psd/move-to-used`, form, {
                          headers: { "Authorization": `Bearer ${getToken()}` },
                        });
                        if (data.moved > 0) {
                          alert(`✓ Moved ${data.moved} photos to:\n${data.used_folder}`);
                        } else {
                          const newFolder = prompt(`No files found in: ${sourceFolder}\nEnter correct folder path:`);
                          if (newFolder) localStorage.setItem("photo_source_folder", newFolder);
                        }
                      } catch (e: any) {
                        alert("Failed: " + (e?.response?.data?.detail || e?.message));
                      }
                    }}
                    className="py-3 px-4 border border-orange-300 bg-orange-50 text-orange-700 rounded-lg font-medium hover:bg-orange-100 text-sm"
                  >
                    📁 Move to Used
                  </button>
                )}
                {resultUrl && (
                  <button onClick={() => updateSession(activeIdx, { resultUrl: null })}
                    className="py-3 px-6 border border-gray-300 rounded-lg font-medium hover:bg-gray-50">
                    ← Edit
                  </button>
                )}
              </div>
            </>
          )}
          </>
          )}
        </>
      )}
    </div>
  );
}
