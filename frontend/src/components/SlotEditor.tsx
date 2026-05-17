"use client";
import { useState } from "react";
import { getToken } from "@/services/auth";
import axios from "axios";

interface Props {
  resultId: string;
  slotIndex: number;
  slotWidth: number;
  slotHeight: number;
  photo: File;
  onDone: (newResultId: string) => void;
  onCancel: () => void;
}

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

export default function SlotEditor({ resultId, slotIndex, slotWidth, slotHeight, photo, onDone, onCancel }: Props) {
  const [zoom, setZoom] = useState(1.0);
  const [offsetX, setOffsetX] = useState(0.0);
  const [offsetY, setOffsetY] = useState(0.0);
  const [rotation, setRotation] = useState(0);
  const [saving, setSaving] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Generate local preview
  const photoUrl = URL.createObjectURL(photo);
  const orientation = slotWidth > slotHeight ? "landscape" : "portrait";

  const handleSave = async () => {
    setSaving(true);
    try {
      const form = new FormData();
      form.append("result_id", resultId);
      form.append("slot_index", slotIndex.toString());
      form.append("zoom", zoom.toString());
      form.append("offset_x", offsetX.toString());
      form.append("offset_y", offsetY.toString());
      form.append("rotation", rotation.toString());
      form.append("photo", photo);

      const { data } = await axios.post(`${getApiBase()}/psd/adjust-slot`, form, {
        headers: { "Content-Type": "multipart/form-data", "Authorization": `Bearer ${getToken()}` },
        timeout: 60000,
      });
      onDone(data.result_id);
    } catch (e: any) {
      alert("Adjustment failed: " + (e?.response?.data?.detail || e?.message));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg space-y-4">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold">Adjust Photo - Slot {slotIndex + 1}</h3>
          <button onClick={onCancel} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        {/* Preview */}
        <div
          className="relative overflow-hidden border rounded-lg mx-auto bg-gray-100"
          style={{
            width: "100%",
            aspectRatio: `${slotWidth} / ${slotHeight}`,
            maxHeight: "300px",
          }}
        >
          <img
            src={photoUrl}
            alt="Adjusting"
            className="absolute"
            style={{
              width: `${zoom * 100}%`,
              height: `${zoom * 100}%`,
              objectFit: "cover",
              left: `${-((zoom - 1) * 50) + offsetX * ((zoom - 1) * 50)}%`,
              top: `${-((zoom - 1) * 50) + offsetY * ((zoom - 1) * 50)}%`,
              transform: `rotate(${rotation}deg)`,
              transformOrigin: "center center",
            }}
          />
        </div>

        {/* Controls */}
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-gray-700 flex justify-between">
              <span>Zoom</span>
              <span className="text-gray-400">{(zoom * 100).toFixed(0)}%</span>
            </label>
            <input
              type="range"
              min="1"
              max="3"
              step="0.05"
              value={zoom}
              onChange={(e) => setZoom(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 flex justify-between">
              <span>Horizontal Position</span>
              <span className="text-gray-400">{offsetX > 0 ? "→" : offsetX < 0 ? "←" : "Center"}</span>
            </label>
            <input
              type="range"
              min="-1"
              max="1"
              step="0.05"
              value={offsetX}
              onChange={(e) => setOffsetX(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 flex justify-between">
              <span>Vertical Position</span>
              <span className="text-gray-400">{offsetY > 0 ? "↓" : offsetY < 0 ? "↑" : "Center"}</span>
            </label>
            <input
              type="range"
              min="-1"
              max="1"
              step="0.05"
              value={offsetY}
              onChange={(e) => setOffsetY(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 flex justify-between">
              <span>Rotation</span>
              <span className="text-gray-400">{rotation}°</span>
            </label>
            <input
              type="range"
              min="-180"
              max="180"
              step="1"
              value={rotation}
              onChange={(e) => setRotation(parseInt(e.target.value))}
              className="w-full"
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={() => { setZoom(1.0); setOffsetX(0); setOffsetY(0); setRotation(0); }}
            className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
          >
            Reset
          </button>
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {saving ? "Applying..." : "Apply Adjustment"}
          </button>
        </div>
      </div>
    </div>
  );
}
