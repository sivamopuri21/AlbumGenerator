"use client";
import { useState, useEffect } from "react";
import Dropzone from "@/components/Dropzone";
import ProgressBar from "@/components/ProgressBar";
import PSDViewer from "@/components/PSDViewer";
import Login from "@/components/Login";
import StoragePanel from "@/components/StoragePanel";
import { isLoggedIn, logout } from "@/services/auth";
import {
  uploadAlbum, getJobStatus, getPageList, getPagePreviewUrl,
  getDownloadZipUrl, getDownloadPdfUrl, BOOK_SIZES, JobStatus, PageList,
} from "@/services/api";

type Step = "upload" | "processing" | "preview" | "download";
type Mode = "psd" | "jpeg";
type Tab = "generate" | "viewer";

export default function Home() {
  const [authenticated, setAuthenticated] = useState(false);
  const [tab, setTab] = useState<Tab>("viewer");
  const [step, setStep] = useState<Step>("upload");
  const [mode, setMode] = useState<Mode>("jpeg");
  const [bookSize, setBookSize] = useState("18x24");
  const [numSheets, setNumSheets] = useState(20);
  const [images, setImages] = useState<File[]>([]);
  const [templates, setTemplates] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [pageList, setPageList] = useState<PageList | null>(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [showStorage, setShowStorage] = useState(false);

  useEffect(() => {
    setAuthenticated(isLoggedIn());
  }, []);

  useEffect(() => {
    if (!jobId || step !== "processing") return;
    const poll = setInterval(async () => {
      try {
        const status = await getJobStatus(jobId);
        setJobStatus(status);
        if (status.status === "completed") {
          clearInterval(poll);
          const pages = await getPageList(jobId);
          setPageList(pages);
          setStep("preview");
        } else if (status.status === "failed") {
          clearInterval(poll);
          setError(status.error || "Processing failed");
        }
      } catch { /* keep polling */ }
    }, 2000);
    return () => clearInterval(poll);
  }, [jobId, step]);

  if (!authenticated) {
    return <Login onLogin={() => setAuthenticated(true)} />;
  }

  const handleSubmit = async () => {
    if (images.length === 0) return setError("Please upload raw photos");
    if (templates.length === 0) return setError("Please upload templates");
    setError(null);
    setStep("processing");
    try {
      const res = await uploadAlbum(bookSize, numSheets, images, templates, setUploadProgress);
      setJobId(res.job_id);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || "Upload failed";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      setStep("upload");
    }
  };

  const reset = () => {
    setStep("upload");
    setImages([]);
    setTemplates([]);
    setUploadProgress(0);
    setJobId(null);
    setJobStatus(null);
    setPageList(null);
    setPreviewPage(1);
    setError(null);
  };

  return (
    <div className="space-y-8">
      {/* Top-level Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          <button
            onClick={() => setTab("viewer")}
            className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === "viewer" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            🔍 PSD Viewer
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowStorage(true)}
            className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
          >
            🗂 Storage
          </button>
          <button
            onClick={() => { logout(); setAuthenticated(false); }}
            className="px-4 py-2 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Storage Panel */}
      {showStorage && <StoragePanel onClose={() => setShowStorage(false)} />}

      {/* PSD Viewer Tab */}
      {tab === "viewer" && <PSDViewer />}

      {/* Generate Album Tab */}
      {tab === "generate" && (
      <div className="space-y-8">
      {/* Step indicator */}
      <div className="flex items-center gap-2 text-sm">
        {(["upload", "processing", "preview", "download"] as Step[]).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            {i > 0 && <div className="w-8 h-px bg-gray-300" />}
            <span className={`px-3 py-1 rounded-full ${
              step === s ? "bg-primary-600 text-white" : "bg-gray-200 text-gray-500"
            }`}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </span>
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {/* Upload Step */}
      {step === "upload" && (
        <div className="space-y-6">
          {/* Mode Tabs */}
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="flex border-b">
              <button
                onClick={() => { setMode("jpeg"); setTemplates([]); }}
                className={`flex-1 py-3 px-6 text-sm font-medium transition-colors ${
                  mode === "jpeg"
                    ? "bg-primary-600 text-white"
                    : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                }`}
              >
                📷 JPEG Album Clone (Mode 2)
              </button>
              <button
                onClick={() => { setMode("psd"); setTemplates([]); }}
                className={`flex-1 py-3 px-6 text-sm font-medium transition-colors ${
                  mode === "psd"
                    ? "bg-primary-600 text-white"
                    : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                }`}
              >
                🎨 PSD Templates (Mode 1)
              </button>
            </div>

            <div className="p-4 bg-gray-50 text-sm text-gray-600">
              {mode === "jpeg" ? (
                <p>Upload existing album pages (JPEG/PNG). The system will detect photo positions, extract the background, and place your new photos in the same layout.</p>
              ) : (
                <p>Upload PSD template files with photo slot layers. The system will extract backgrounds and place photos into the detected slots.</p>
              )}
            </div>
          </div>

          {/* Album Configuration */}
          <div className="bg-white rounded-xl shadow-sm border p-6 space-y-6">
            <h2 className="text-lg font-semibold">Album Configuration</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Book Size</label>
                <select
                  value={bookSize}
                  onChange={(e) => setBookSize(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                >
                  {BOOK_SIZES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Number of Sheets</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={numSheets}
                  onChange={(e) => setNumSheets(parseInt(e.target.value) || 1)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-400 mt-1">{numSheets * 2} pages total</p>
              </div>
            </div>
          </div>

          {/* File Uploads */}
          <div className="bg-white rounded-xl shadow-sm border p-6 space-y-6">
            <h2 className="text-lg font-semibold">Upload Files</h2>

            {mode === "jpeg" ? (
              <Dropzone
                label="Existing Album Pages (JPEG/PNG)"
                accept={{ "image/jpeg": [".jpg", ".jpeg"], "image/png": [".png"] }}
                files={templates}
                onFiles={setTemplates}
                maxFiles={100}
                hint="Upload finished album pages — system will clone the layout and replace photos"
              />
            ) : (
              <Dropzone
                label="PSD Templates"
                accept={{ "application/octet-stream": [".psd"], "image/vnd.adobe.photoshop": [".psd"] }}
                files={templates}
                onFiles={setTemplates}
                maxFiles={100}
                hint="Upload PSD files with photo slot layers (named 'photo_1', 'slot_1', etc.)"
              />
            )}

            <Dropzone
              label="Raw Photos"
              accept={{ "image/*": [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"] }}
              files={images}
              onFiles={setImages}
              maxFiles={1000}
              hint="JPG, PNG, WebP — the new photos to place in the album"
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={images.length === 0 || templates.length === 0}
            className="w-full py-3 px-6 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Generate Album ({images.length} photos, {templates.length} templates, {numSheets} sheets)
          </button>
        </div>
      )}

      {/* Processing Step */}
      {step === "processing" && (
        <div className="bg-white rounded-xl shadow-sm border p-8 space-y-6">
          <h2 className="text-lg font-semibold">Generating Your Album</h2>
          {jobStatus ? (
            <ProgressBar progress={jobStatus.progress} status={jobStatus.status} message={jobStatus.message} />
          ) : (
            <ProgressBar progress={uploadProgress} status="uploading" message="Uploading files..." />
          )}
          {jobStatus && (
            <div className="text-sm text-gray-500 space-y-1">
              <p>Book: {jobStatus.book_size} | Sheets: {jobStatus.total_sheets} | Pages: {jobStatus.total_pages}</p>
            </div>
          )}
        </div>
      )}

      {/* Preview Step */}
      {step === "preview" && jobId && pageList && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="p-4 border-b flex justify-between items-center">
              <h2 className="text-lg font-semibold">Album Preview</h2>
              <span className="text-sm text-gray-500">{pageList.total_pages} pages</span>
            </div>
            <div className="p-4">
              <img
                src={getPagePreviewUrl(jobId, previewPage)}
                alt={`Page ${previewPage}`}
                className="w-full h-auto rounded shadow"
              />
            </div>
            <div className="p-4 border-t flex items-center justify-between">
              <button
                onClick={() => setPreviewPage(Math.max(1, previewPage - 1))}
                disabled={previewPage <= 1}
                className="px-4 py-2 border rounded-lg disabled:opacity-30"
              >
                ← Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {previewPage} of {pageList.total_pages}
              </span>
              <button
                onClick={() => setPreviewPage(Math.min(pageList.total_pages, previewPage + 1))}
                disabled={previewPage >= pageList.total_pages}
                className="px-4 py-2 border rounded-lg disabled:opacity-30"
              >
                Next →
              </button>
            </div>
          </div>
          <div className="flex gap-4">
            <button
              onClick={() => setStep("download")}
              className="flex-1 py-3 px-6 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors"
            >
              Download Album
            </button>
            <button onClick={reset} className="py-3 px-6 border border-gray-300 rounded-lg font-medium hover:bg-gray-50">
              Start Over
            </button>
          </div>
        </div>
      )}

      {/* Download Step */}
      {step === "download" && jobId && (
        <div className="bg-white rounded-xl shadow-sm border p-8 text-center space-y-6">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
            <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold">Your Album is Ready!</h2>
          <p className="text-gray-500">
            {jobStatus?.total_pages || 0} pages at {jobStatus?.book_size} | Includes PDF + JPEG + PSD files
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <a
              href={getDownloadZipUrl(jobId)}
              className="py-3 px-8 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors"
            >
              Download ZIP (All Formats)
            </a>
            <a
              href={getDownloadPdfUrl(jobId)}
              className="py-3 px-6 border border-gray-300 rounded-lg font-medium hover:bg-gray-50"
            >
              Download PDF Only
            </a>
          </div>
          <div className="flex gap-4 justify-center">
            <button onClick={() => setStep("preview")} className="text-sm text-gray-500 hover:text-gray-700">
              Back to Preview
            </button>
            <button onClick={reset} className="text-sm text-gray-500 hover:text-gray-700">
              Create Another Album
            </button>
          </div>
        </div>
      )}
    </div>
    )}
    </div>
  );
}
