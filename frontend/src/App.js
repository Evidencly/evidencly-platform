import React, { useState, useCallback, useRef, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import axios from "axios";
import "./App.css";

const API_BASE = "/api";

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [seedId, setSeedId] = useState(null);
  const [searchAddress, setSearchAddress] = useState("");
  const [depth, setDepth] = useState(3);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredEdge, setHoveredEdge] = useState(null);
  const [activeTab, setActiveTab] = useState("graph");
  const [ingestionStatus, setIngestionStatus] = useState(null);
  const [narrative, setNarrative] = useState("");
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [attesting, setAttesting] = useState(false);
  const [sourceType, setSourceType] = useState("DOJ_FBI");
  const [investigationNotes, setInvestigationNotes] = useState("");
  const [attachedEvidence, setAttachedEvidence] = useState([]);
  const [crossCaseCount, setCrossCaseCount] = useState(0);
  const [nodeNote, setNodeNote] = useState("");
  const [annotationOpen, setAnnotationOpen] = useState(false);
  const [annotationSaving, setAnnotationSaving] = useState(false);
  const [annotationDirty, setAnnotationDirty] = useState(false);
  const [webResults, setWebResults] = useState([]);
  const [twitterResults, setTwitterResults] = useState([]);
  const [breadcrumbLabels, setBreadcrumbLabels] = useState([]);
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [cases, setCases] = useState([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [savingCase, setSavingCase] = useState(false);
  const [caseName, setCaseName] = useState("");
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [clusterInfo, setClusterInfo] = useState({ size: 0, components: 0 });

  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const pollingInterval = useRef(null);
  const transform = useRef({ x: 0, y: 0, scale: 1 }).current;
  const hoveredEdgeRef = useRef(null);
  const dragMovedRef = useRef(false);

  const findSeedNode = (nodes, edges) => {
    if (!nodes.length) return null;
    if (seedId) return nodes.find(n => n.id === seedId) || nodes[0];
    const outgoing = {};
    edges.forEach(edge => { outgoing[edge.source] = (outgoing[edge.source] || 0) + 1; });
    let best = nodes[0];
    let max = -1;
    nodes.forEach(node => {
      const cnt = outgoing[node.id] || 0;
      if (cnt > max) { max = cnt; best = node; }
    });
    return best;
  };

    const computeRadialLayout = (nodes, edges, seedId) => {
    const positions = new Map();
    const radii = { 1: 200, 2: 380, 3: 520 };
    const adj = new Map();
    nodes.forEach(n => adj.set(String(n.id), []));
    edges.forEach(e => {
      adj.get(String(e.source))?.push(String(e.target));
      adj.get(String(e.target))?.push(String(e.source));
    });
    const seedIdStr = String(seedId);
    const levels = new Map();
    levels.set(seedIdStr, 0);
    const queue = [seedIdStr];
    while (queue.length) {
      const current = queue.shift();
      const curLevel = levels.get(current);
      if (curLevel >= 3) continue;
      for (const nb of (adj.get(current) || [])) {
        if (!levels.has(nb)) {
          levels.set(nb, curLevel + 1);
          queue.push(nb);
        }
      }
    }
    const levelGroups = { 1: [], 2: [], 3: [] };
    nodes.forEach(node => {
      const nodeId = String(node.id);
      if (nodeId === seedIdStr) return;
      const lvl = levels.has(nodeId) ? levels.get(nodeId) : 3;
      levelGroups[Math.min(Math.max(lvl, 1), 3)].push(node);
    });
    positions.set(seedIdStr, { x: 0, y: 0, level: 0 });
    const angleStep1 = (2 * Math.PI) / Math.max(levelGroups[1].length, 1);
    levelGroups[1].forEach((node, idx) => {
      const angle = idx * angleStep1;
      positions.set(String(node.id), { x: radii[1] * Math.cos(angle), y: radii[1] * Math.sin(angle), level: 1 });
    });
    const angleStep2 = (2 * Math.PI) / Math.max(levelGroups[2].length, 1);
    levelGroups[2].forEach((node, idx) => {
      const angle = idx * angleStep2;
      positions.set(String(node.id), { x: radii[2] * Math.cos(angle), y: radii[2] * Math.sin(angle), level: 2 });
    });
    const angleStep3 = (2 * Math.PI) / Math.max(levelGroups[3].length, 1);
    levelGroups[3].forEach((node, idx) => {
      const angle = idx * angleStep3;
      positions.set(String(node.id), { x: radii[3] * Math.cos(angle), y: radii[3] * Math.sin(angle), level: 3 });
    });
    return positions;
  };

  const drawGraph = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (!graphData.nodes.length) return;
    ctx.save();
    ctx.translate(transform.x + w / 2, transform.y + h / 2);
    ctx.scale(transform.scale, transform.scale);
    const seed = findSeedNode(graphData.nodes, graphData.edges);
    if (!seed) { ctx.restore(); return; }
    const positions = computeRadialLayout(graphData.nodes, graphData.edges, seed.id);
    const hEdge = hoveredEdgeRef.current;

    // Draw edges — labels only on hover
    graphData.edges.forEach(edge => {
      const from = positions.get(edge.source);
      const to = positions.get(edge.target);
      if (!from || !to) return;
      const isHovered = hEdge && hEdge === edge;
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      let color = "rgba(136,136,136,0.4)";
      if (edge.type === "ATTRIBUTED_TO") color = isHovered ? "#2dd4bf" : "rgba(45,212,191,0.5)";
      else if (edge.type === "MIXED_THROUGH") color = isHovered ? "#ff4444" : "rgba(255,68,68,0.4)";
      else if (isHovered) color = "rgba(200,200,200,0.9)";
      ctx.strokeStyle = color;
      ctx.lineWidth = isHovered ? 2.5 : (edge.type === "ATTRIBUTED_TO" ? 1.5 : 1);
      if (isHovered && edge.type === "ATTRIBUTED_TO") { ctx.shadowBlur = 10; ctx.shadowColor = "#2dd4bf"; }
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Only draw label on hover
      if (isHovered && edge.amount_eth) {
        const mx = (from.x + to.x) / 2;
        const my = (from.y + to.y) / 2;
        ctx.font = "bold 11px Inter";
        ctx.fillStyle = "#ffffff";
        ctx.shadowBlur = 4;
        ctx.shadowColor = "#000000";
        ctx.fillText(edge.amount_eth.toFixed(4) + " ETH", mx + 4, my - 4);
        ctx.shadowBlur = 0;
      }
    });

    // Draw nodes
    graphData.nodes.forEach(node => {
      const pos = positions.get(node.id);
      if (!pos) return;
      const isSeed = node.id === seed.id;
      const level = pos.level;

      // Opacity by hop level
      const opacity = isSeed ? 1 : level === 1 ? 0.9 : level === 2 ? 0.65 : 0.4;

      let color = `rgba(136,153,170,${opacity})`;
      if (isSeed) color = "#2dd4bf";
      else if (node.risk_level === "High") color = `rgba(255,68,68,${opacity})`;
      else if (node.entity_type === "Exchange") color = `rgba(68,255,136,${opacity})`;
      else if (node.entity_type === "Mixer") color = `rgba(255,136,68,${opacity})`;
      else if (node.entity_type === "Sanctioned") color = `rgba(255,0,0,${opacity})`;
      else if (node.type === "Organization") color = `rgba(68,136,255,${opacity})`;
      else if (node.type === "SmartContract") color = `rgba(170,68,255,${opacity})`;
      else if (node.confidence > 0.7) color = `rgba(255,170,68,${opacity})`;

      // Size by level
      let size = isSeed ? 20 : level === 1 ? 7 : level === 2 ? 5 : 4;
      if (!isSeed && node.risk_level === "High") size = Math.max(size, 10);
      else if (!isSeed && node.entity_type === "Exchange") size = Math.max(size, 9);

      // Seed glow
      if (isSeed) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size + 8, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(45,212,191,0.15)";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size + 4, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(45,212,191,0.25)";
        ctx.fill();
        ctx.shadowBlur = 20;
        ctx.shadowColor = "#2dd4bf";
      }

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.shadowBlur = 0;

      if (selectedNode && selectedNode.id === node.id) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size + 3, 0, 2 * Math.PI);
        ctx.strokeStyle = "white";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Labels: seed always, enriched nodes only at hop1
      if (isSeed) {
        const label = node.label || (node.address ? node.address.slice(0, 6) + "..." + node.address.slice(-4) : "");
        ctx.font = "bold 12px Inter";
        ctx.fillStyle = "#2dd4bf";
        ctx.fillText(label || "Seed", pos.x + size + 4, pos.y + 4);
      } else if (node.enriched === true && level === 1) {
        const label = node.label || (node.address ? node.address.slice(0, 6) + "..." : "");
        if (label) {
          ctx.font = "11px Inter";
          ctx.fillStyle = `rgba(226,232,240,${opacity})`;
          ctx.fillText(label, pos.x + size + 2, pos.y + 4);
        }
      }
    });
    ctx.restore();
  }, [graphData, selectedNode, transform]);

  // Canvas resize, zoom, pan, hover
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const resizeObserver = new ResizeObserver(() => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      drawGraph();
    });
    resizeObserver.observe(container);
    const handleWheel = (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      transform.scale *= delta;
      transform.scale = Math.min(Math.max(transform.scale, 0.2), 4);
      drawGraph();
    };
    let isPanning = false;
    let lastX, lastY;
    const handleMouseDown = (e) => { isPanning = true; dragMovedRef.current = false; lastX = e.clientX; lastY = e.clientY; canvas.style.cursor = "grabbing"; };
    const handleMouseMove = (e) => {
      if (isPanning) {
        const dx = e.clientX - lastX;
        const dy = e.clientY - lastY;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMovedRef.current = true;
        transform.x += dx;
        transform.y += dy;
        lastX = e.clientX;
        lastY = e.clientY;
        drawGraph();
        return;
      }
      // Edge hover detection
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const mouseX = (e.clientX - rect.left) * scaleX;
      const mouseY = (e.clientY - rect.top) * scaleY;
      const cx = (mouseX - (transform.x + canvas.width / 2)) / transform.scale;
      const cy = (mouseY - (transform.y + canvas.height / 2)) / transform.scale;
      const seed = findSeedNode(graphData.nodes, graphData.edges);
      if (!seed || !graphData.nodes.length) return;
      const positions = computeRadialLayout(graphData.nodes, graphData.edges, seed.id);
      let found = null;
      for (const edge of graphData.edges) {
        const from = positions.get(edge.source);
        const to = positions.get(edge.target);
        if (!from || !to) continue;
        // Point-to-segment distance
        const dx = to.x - from.x, dy = to.y - from.y;
        const len2 = dx * dx + dy * dy;
        if (len2 === 0) continue;
        const t = Math.max(0, Math.min(1, ((cx - from.x) * dx + (cy - from.y) * dy) / len2));
        const px = from.x + t * dx - cx;
        const py = from.y + t * dy - cy;
        const dist = Math.sqrt(px * px + py * py);
        if (dist < 8 / transform.scale) { found = edge; break; }
      }
      if (found !== hoveredEdgeRef.current) {
        hoveredEdgeRef.current = found;
        canvas.style.cursor = found ? "crosshair" : (isPanning ? "grabbing" : "grab");
        drawGraph();
      }
    };
    const handleMouseUp = () => { isPanning = false; canvas.style.cursor = "grab"; };
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    canvas.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    canvas.style.cursor = "grab";
    return () => {
      resizeObserver.disconnect();
      canvas.removeEventListener("wheel", handleWheel);
      canvas.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [drawGraph, graphData]);

  useEffect(() => { drawGraph(); }, [graphData, drawGraph]);

  const handleCanvasClick = (e) => {
    if (dragMovedRef.current) { dragMovedRef.current = false; return; }
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const mouseX = (e.clientX - rect.left) * scaleX;
    const mouseY = (e.clientY - rect.top) * scaleY;
    const cx = (mouseX - (transform.x + canvas.width / 2)) / transform.scale;
    const cy = (mouseY - (transform.y + canvas.height / 2)) / transform.scale;
    const seed = findSeedNode(graphData.nodes, graphData.edges);
    if (!seed) return;
    const positions = computeRadialLayout(graphData.nodes, graphData.edges, seed.id);
    let closest = null;
    let minDist = 20 / transform.scale;
    graphData.nodes.forEach(node => {
      const pos = positions.get(node.id);
      if (!pos) return;
      const isSeed = node.id === seed.id;
      const level = pos.level;
      let size = isSeed ? 20 : level === 1 ? 7 : level === 2 ? 5 : 4;
      if (!isSeed && node.risk_level === "High") size = Math.max(size, 10);
      const dx = pos.x - cx, dy = pos.y - cy;
      const dist = Math.hypot(dx, dy);
      if (dist < minDist && dist < size + 4) { minDist = dist; closest = node; }
    });
    if (closest) {
      setSelectedNode(closest);
      setAnnotationOpen(false);
      setAnnotationDirty(false);
      if (closest.address) {
        axios.get(API_BASE + "/annotations/" + closest.address)
          .then(r => setNodeNote(r.data.note || ""))
          .catch(() => setNodeNote(""));
      } else {
        setNodeNote("");
      }
    }
  };

  const startPolling = (address) => {
    if (pollingInterval.current) clearInterval(pollingInterval.current);
    pollingInterval.current = setInterval(async () => {
      try {
        const res = await axios.get(`${API_BASE}/search/${address}/status`);
        setIngestionStatus(res.data);
        if (res.data.status === "complete") {
          clearInterval(pollingInterval.current);
          pollingInterval.current = null;
          handleSearch(false);
        }
      } catch (err) { console.error("Polling error", err); }
    }, 3000);
  };

  const handleSearch = async (showLoading = true) => {
    if (!searchAddress.trim()) return;
    if (showLoading) setSearching(true);
    setError(null);
    if (showLoading) setSelectedNode(null);
    setCrossCaseCount(0);
    setWebResults([]);
    setTwitterResults([]);
    setBreadcrumbLabels([]);
    setClusterInfo({ size: 0, components: 0 });
    setAttachedEvidence([]);
    setNarrative("");
    try {
      const res = await axios.post(`${API_BASE}/search`, { wallet_address: searchAddress.trim(), depth: depth });
      setGraphData({ nodes: res.data.nodes, edges: res.data.edges });
      setSeedId(res.data.seed_id || null);
      setCrossCaseCount(res.data.cross_case_count || 0);
      if (res.data.ingestion_id) {
        startPolling(searchAddress.trim());
      } else {
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        setIngestionStatus({ status: "complete" });
      }
      const mentionEdges = res.data.edges.filter(e => e.type === "MENTIONED_IN");
      const webR = mentionEdges.flatMap(e => e.evidence || []).filter(ev => ev.url && !ev.url.includes("twitter"));
      const twitR = mentionEdges.flatMap(e => e.evidence || []).filter(ev => ev.url && ev.url.includes("twitter"));
      setWebResults(webR);
      setTwitterResults(twitR);
      const labels = res.data.nodes.flatMap(n => n.metadata?.labels || []).slice(0, 10);
      setBreadcrumbLabels(labels);
      setClusterInfo({ size: res.data.nodes.length, components: 1 });
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "Search failed");
      setGraphData({ nodes: [], edges: [] });
    } finally { if (showLoading) setSearching(false); }
  };

  const handleKeyPress = (e) => { if (e.key === "Enter") handleSearch(); };

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file || file.type !== "application/pdf") { alert("Please upload a PDF file"); return; }
    setAttesting(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("source_type", sourceType);
    try {
      const res = await axios.post(`${API_BASE}/attest`, formData, { headers: { "Content-Type": "multipart/form-data" } });
      setAttachedEvidence(prev => [...prev, { source_type: sourceType, hash: res.data.source_hash, addresses_matched: res.data.addresses_matched }]);
      alert(`Attestation complete. Matched ${res.data.addresses_matched} addresses.`);
      handleSearch(false);
    } catch (err) { alert("Attestation failed: " + (err.response?.data?.detail || err.message)); }
    finally { setAttesting(false); }
  }, [sourceType]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: { "application/pdf": [] } });

  const generateNarrative = async () => {
    if (!graphData.nodes.length) { alert("No graph data to analyze"); return; }
    setNarrativeLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/narrative`, { nodes: graphData.nodes, edges: graphData.edges });
      setNarrative(res.data.narrative);
    } catch (err) { console.error(err); setNarrative("Error generating narrative"); }
    finally { setNarrativeLoading(false); }
  };

  const exportReport = async () => {
    if (!graphData.nodes.length) { alert("No data to export"); return; }
    setExportLoading(true);
    try {
      const formData = new FormData();
      formData.append("graph_data", JSON.stringify(graphData));
      formData.append("narrative", narrative || "");
      formData.append("notes", investigationNotes || "");
      formData.append("case_name", caseName || (searchAddress ? searchAddress.slice(0,12) + " Investigation" : "Investigation"));
      formData.append("address", searchAddress || "");
      const res = await axios.post(`${API_BASE}/export`, formData, {
        responseType: "blob",
        timeout: 30000
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "evidencly_" + (searchAddress ? searchAddress.slice(0,8) : "report") + "_" + Date.now() + ".pdf");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export error:", err);
      alert("Export failed: " + (err.message || "unknown error"));
    }
    finally { setExportLoading(false); }
  };

  const fetchTimeline = async () => {
    setTimelineLoading(true);
    try {
      const res = await axios.get(API_BASE + "/timeline");
      setTimelineEvents(res.data.events || []);
    } catch(e) { console.error(e); }
    setTimelineLoading(false);
  };

  const fetchCases = async () => {
    setCasesLoading(true);
    try {
      const res = await axios.get(API_BASE + "/investigations");
      setCases(res.data.investigations || []);
    } catch(e) { console.error(e); }
    setCasesLoading(false);
  };

  const saveCase = async () => {
    if (!caseName.trim() || !graphData.nodes.length) return;
    setSavingCase(true);
    try {
      const res = await axios.post(API_BASE + "/investigation/create", {
        name: caseName.trim(),
        starting_address: searchAddress
      });
      const inv_id = res.data.investigation_id;
      await axios.post(API_BASE + "/investigation/" + inv_id + "/save", {
        nodes: graphData.nodes,
        edges: graphData.edges,
        narrative: narrative
      });
      setCaseName("");
      setShowSaveForm(false);
      fetchCases();
    } catch(e) { console.error(e); }
    setSavingCase(false);
  };

  const loadCase = async (inv) => {
    try {
      const res = await axios.get(API_BASE + "/investigation/" + inv.investigation_id);
      setSearchAddress(res.data.starting_address || "");
      if (res.data.nodes && res.data.nodes.length) {
        setGraphData({ nodes: res.data.nodes, edges: res.data.edges || [] });
      }
      if (res.data.narrative) setNarrative(res.data.narrative);
      setActiveTab("graph");
    } catch(e) { console.error(e); }
  };

  const deleteCase = async (inv_id) => {
    try {
      await axios.delete(API_BASE + "/investigation/" + inv_id);
      fetchCases();
    } catch(e) { console.error(e); }
  };

  const getConfidenceBarClass = (confidence) => {
    if (confidence >= 0.8) return "bar-high";
    if (confidence >= 0.5) return "bar-medium";
    return "bar-low";
  };
  const formatConfidence = (confidence) => `${Math.round(confidence * 100)}%`;

  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <img src="/logo.png" alt="Evidencly" className="logo-img" />
          <span className="logo-text">Evidencly</span>
          <span className="tagline">Evidence on Chain</span>
        </div>
        <div className="header-tabs">
          <button className={activeTab === "graph" ? "header-tab active" : "header-tab"} onClick={() => setActiveTab("graph")}>Graph</button>
          <button className={activeTab === "intel" ? "header-tab active" : "header-tab"} onClick={() => setActiveTab("intel")}>Intel</button>
          <button className={activeTab === "evidence" ? "header-tab active" : "header-tab"} onClick={() => setActiveTab("evidence")}>Evidence</button>
          <button className={activeTab === "narrative" ? "header-tab active" : "header-tab"} onClick={() => setActiveTab("narrative")}>Narrative</button>
          <button className={activeTab === "timeline" ? "header-tab active" : "header-tab"} onClick={() => { setActiveTab("timeline"); fetchTimeline(); }}>Timeline</button>
          <button className={activeTab === "cases" ? "header-tab active" : "header-tab"} onClick={() => { setActiveTab("cases"); fetchCases(); }}>Cases</button>
        </div>
        <div className="header-links">
          <a href="https://github.com/evidencly/evidencly" target="_blank" rel="noopener noreferrer">GitHub</a>
        </div>
      </header>

      <div className="search-bar">
        <input type="text" placeholder="Enter wallet address (0x...)" value={searchAddress} onChange={(e) => setSearchAddress(e.target.value)} onKeyPress={handleKeyPress} disabled={searching} />
        <select value={depth} onChange={(e) => setDepth(parseInt(e.target.value))}>
          <option value={2}>2 hops</option>
          <option value={3}>3 hops</option>
          <option value={5}>5 hops</option>
          <option value={7}>7 hops</option>
          <option value={10}>10 hops</option>
        </select>
        <button onClick={() => handleSearch()} disabled={searching}>{searching ? "Investigating..." : "Investigate"}</button>
      </div>

      {ingestionStatus && ingestionStatus.status !== "complete" && (
        <div className="status-strip">
          <span className="status-icon">⟳</span>
          <span>Investigating... </span>
          {ingestionStatus.sources_complete?.map(s => (<span key={s} className="status-badge">✓ {s}</span>))}
          {ingestionStatus.sources_pending?.map(s => (<span key={s} className="status-badge pending">⟳ {s}</span>))}
        </div>
      )}

      <div className="main-content">
        <div className="graph-container" ref={containerRef}>
          <canvas ref={canvasRef} onClick={handleCanvasClick} style={{ width: "100%", height: "100%", display: "block" }} />
          <div className="legend">
            <div className="legend-item"><div className="legend-dot" style={{backgroundColor:"#2dd4bf"}}></div>Seed</div>
            <div className="legend-item"><div className="legend-dot" style={{backgroundColor:"rgba(68,255,136,0.9)"}}></div>Exchange</div>
            <div className="legend-item"><div className="legend-dot" style={{backgroundColor:"rgba(255,136,68,0.9)"}}></div>Mixer</div>
            <div className="legend-item"><div className="legend-dot" style={{backgroundColor:"rgba(255,0,0,0.9)"}}></div>Sanctioned</div>
            <div className="legend-item"><div className="legend-dot" style={{backgroundColor:"rgba(68,136,255,0.9)"}}></div>Organisation</div>
            <div className="legend-item"><div className="legend-dot" style={{backgroundColor:"rgba(170,68,255,0.9)"}}></div>Smart Contract</div>
            <div className="legend-item"><div className="legend-dot" style={{backgroundColor:"rgba(255,170,68,0.9)"}}></div>High Confidence</div>
            <div className="legend-item"><div className="legend-dot" style={{backgroundColor:"rgba(136,153,170,0.9)"}}></div>Wallet</div>
          </div>
          {graphData.nodes.length === 0 && !searching && !error && (
            <div className="empty-graph-overlay"><p>🔍 Enter a wallet address to begin investigation</p></div>
          )}
          {searching && (<div className="loading-overlay"><div className="spinner"></div><p>Loading graph...</p></div>)}
          {error && (<div className="error-overlay"><p>⚠️ {error}</p></div>)}
        </div>

        <div className="sidebar">
          {activeTab === "graph" && (
            <>
              {selectedNode && (
                <div className="node-details">
                  <h3>Entity Details</h3>
                  {selectedNode.risk_level && selectedNode.risk_level !== "Unknown" && selectedNode.label && selectedNode.label !== "Unlabeled" && (
                    <div style={{
                      marginBottom: '12px',
                      padding: '10px',
                      borderRadius: '6px',
                      border: `2px solid ${selectedNode.risk_level === 'Critical' ? '#dc2626' : selectedNode.risk_level === 'High' ? '#f97316' : selectedNode.risk_level === 'Medium' ? '#f59e0b' : '#10b981'}`,
                      backgroundColor: selectedNode.risk_level === 'Critical' ? 'rgba(220,38,38,0.1)' : selectedNode.risk_level === 'High' ? 'rgba(249,115,22,0.1)' : 'rgba(16,185,129,0.1)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                        <span>⚠️</span>
                        <span style={{ fontWeight: 'bold', fontSize: '13px' }}>Known Entity</span>
                        <span style={{
                          padding: '1px 6px', borderRadius: '3px', fontSize: '11px', fontWeight: 'bold',
                          backgroundColor: selectedNode.risk_level === 'Critical' ? '#dc2626' : selectedNode.risk_level === 'High' ? '#f97316' : '#10b981',
                          color: 'white'
                        }}>{selectedNode.risk_level} RISK</span>
                      </div>
                      <div style={{ fontSize: '12px', opacity: 0.9 }}>
                        {selectedNode.label} — {selectedNode.entity_type}
                      </div>
                    </div>
                  )}
                  <p><strong>Address:</strong> {selectedNode.address || "N/A"}</p>
                  <p><strong>Label:</strong> {selectedNode.label || "Unlabeled"}</p>
                  <p><strong>Type:</strong> {selectedNode.entity_type || selectedNode.type || "Unknown"}</p>
                  <p><strong>Risk:</strong> {selectedNode.risk_level || "Unknown"}</p>
                  <p><strong>Confidence:</strong> {formatConfidence(selectedNode.confidence || 0)}</p>
                  <div className="confidence-bar-container"><div className={`confidence-bar ${getConfidenceBarClass(selectedNode.confidence || 0)}`} style={{ width: `${(selectedNode.confidence || 0) * 100}%` }} /></div>
                  {selectedNode.source_type && <p><strong>Source:</strong> {selectedNode.source_type}</p>}
                  <div className="annotation-section">
                    {!annotationOpen ? (
                      <button className="add-note-btn" onClick={() => setAnnotationOpen(true)}>
                        {nodeNote ? "✏️ Edit Note" : "📝 Add Note"}
                        {nodeNote && <span className="note-indicator"> •</span>}
                      </button>
                    ) : (
                      <div className="annotation-panel">
                        <div className="annotation-header">
                          <span>📝 Investigator Note</span>
                          <button className="annotation-close" onClick={() => { setAnnotationOpen(false); setAnnotationDirty(false); }}>✕</button>
                        </div>
                        <textarea
                          className="annotation-textarea"
                          placeholder="Add your note about this address..."
                          value={nodeNote}
                          onChange={e => { setNodeNote(e.target.value); setAnnotationDirty(true); }}
                          rows={4}
                        />
                        <div className="annotation-actions">
                          <button
                            className="annotation-save-btn"
                            disabled={annotationSaving || !annotationDirty}
                            onClick={async () => {
                              setAnnotationSaving(true);
                              try {
                                await axios.post(API_BASE + "/annotations", {
                                  node_id: selectedNode.id,
                                  address: selectedNode.address,
                                  note: nodeNote
                                });
                                setAnnotationDirty(false);
                                setAnnotationOpen(false);
                              } catch(e) { console.error(e); }
                              setAnnotationSaving(false);
                            }}
                          >{annotationSaving ? "Saving..." : "Save Note"}</button>
                          {nodeNote && (
                            <button
                              className="annotation-delete-btn"
                              onClick={async () => {
                                await axios.delete(API_BASE + "/annotations/" + selectedNode.address);
                                setNodeNote("");
                                setAnnotationDirty(false);
                                setAnnotationOpen(false);
                              }}
                            >Delete</button>
                          )}
                        </div>
                      </div>
                    )}
                    {nodeNote && !annotationOpen && (
                      <div className="note-preview">💬 {nodeNote.length > 80 ? nodeNote.slice(0, 80) + "…" : nodeNote}</div>
                    )}
                  </div>
                  {crossCaseCount > 0 && <div className="cross-case-badge">⚠️ Appears in {crossCaseCount} other investigations</div>}
                </div>
              )}
              {!selectedNode && <div className="node-details"><p>Click a node to see details</p></div>}
            </>
          )}

          {activeTab === "timeline" && (
            <div className="timeline-panel">
              <div className="timeline-header">
                <h3>Transaction Timeline</h3>
                <button className="timeline-refresh-btn" onClick={fetchTimeline} disabled={timelineLoading}>
                  {timelineLoading ? "Loading..." : "↻ Refresh"}
                </button>
              </div>
              {timelineLoading && <p className="timeline-empty">Loading timeline...</p>}
              {!timelineLoading && timelineEvents.length === 0 && (
                <div className="timeline-empty-state">
                  <p>No timestamped transactions yet.</p>
                  <p className="timeline-hint">Run an investigation to populate the timeline with real block timestamps.</p>
                </div>
              )}
              {!timelineLoading && timelineEvents.length > 0 && (
                <div className="timeline-list">
                  {timelineEvents.map((ev, i) => (
                    <div key={ev.id} className="timeline-event">
                      <div className="timeline-dot" />
                      <div className="timeline-content">
                        <div className="timeline-time">
                          {new Date(ev.timestamp).toUTCString().replace(" GMT", " UTC")}
                        </div>
                        <div className="timeline-flow">
                          <span className={`timeline-entity ${ev.source_type === "Exchange" ? "entity-exchange" : ev.source_type === "Mixer" ? "entity-mixer" : ""}`}>
                            {ev.source_label !== "Unlabeled" ? ev.source_label : ev.source_address.slice(0,8) + "…" + ev.source_address.slice(-4)}
                          </span>
                          <span className="timeline-arrow">→</span>
                          <span className={`timeline-entity ${ev.target_type === "Exchange" ? "entity-exchange" : ev.target_type === "Mixer" ? "entity-mixer" : ""}`}>
                            {ev.target_label !== "Unlabeled" ? ev.target_label : ev.target_address.slice(0,8) + "…" + ev.target_address.slice(-4)}
                          </span>
                        </div>
                        <div className="timeline-meta">
                          <span className="timeline-amount">Ξ {ev.amount_eth.toFixed(4)}</span>
                          {ev.tx_hash && (
                            <a className="timeline-txlink" href={"https://etherscan.io/tx/" + ev.tx_hash} target="_blank" rel="noopener noreferrer">
                              {ev.tx_hash.slice(0,10)}…
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === "cases" && (
            <div className="cases-panel">
              <div className="cases-header">
                <h3>Case Files</h3>
                <button className="cases-save-btn" onClick={() => setShowSaveForm(!showSaveForm)} disabled={!graphData.nodes.length}>
                  {showSaveForm ? "✕ Cancel" : "💾 Save Current"}
                </button>
              </div>
              {showSaveForm && (
                <div className="cases-save-form">
                  <input
                    className="cases-name-input"
                    placeholder="Case name..."
                    value={caseName}
                    onChange={e => setCaseName(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && saveCase()}
                  />
                  <button className="cases-confirm-btn" onClick={saveCase} disabled={savingCase || !caseName.trim()}>
                    {savingCase ? "Saving..." : "Save"}
                  </button>
                </div>
              )}
              {casesLoading && <p className="cases-empty">Loading...</p>}
              {!casesLoading && cases.length === 0 && (
                <div className="cases-empty-state">
                  <p>No saved cases yet.</p>
                  <p className="cases-hint">Run an investigation then save it as a case file.</p>
                </div>
              )}
              {!casesLoading && cases.length > 0 && (
                <div className="cases-list">
                  {cases.map(inv => (
                    <div key={inv.investigation_id} className="case-item">
                      <div className="case-info" onClick={() => loadCase(inv)}>
                        <div className="case-name">{inv.name}</div>
                        <div className="case-meta">
                          <span>{inv.starting_address ? inv.starting_address.slice(0,8) + "…" : "—"}</span>
                          <span>{inv.node_count} nodes · {inv.edge_count} edges</span>
                        </div>
                        <div className="case-date">{new Date(inv.updated_at).toLocaleDateString()}</div>
                      </div>
                      <button className="case-delete-btn" onClick={() => deleteCase(inv.investigation_id)}>✕</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === "intel" && (
            <div className="intel-panel">
              <div className="intel-section">
                <h4>🌐 Web Results</h4>
                {webResults.length > 0 ? webResults.map((r, i) => <p key={i}><a href={r.url} target="_blank" rel="noopener noreferrer">{r.title || "Link"}</a></p>) : <p className="intel-empty">No web results found</p>}
              </div>
              <div className="intel-section">
                <h4>🐦 Social Mentions</h4>
                {twitterResults.length > 0 ? twitterResults.map((t, i) => <p key={i}><a href={t.url} target="_blank" rel="noopener noreferrer">{t.text || "Tweet"}</a></p>) : <p className="intel-empty">No social mentions found</p>}
              </div>
              <div className="intel-section">
                <h4>🏷️ Entity Labels</h4>
                {breadcrumbLabels.length > 0 ? breadcrumbLabels.map((l, i) => <p key={i}>🔖 {l}</p>) : <p className="intel-empty">No entity labels found</p>}
              </div>
              <div className="intel-section">
                <h4>🔗 Cluster Analysis</h4>
                <p>Cluster size: {clusterInfo.size}</p>
                <p>Connected components: {clusterInfo.components}</p>
              </div>
            </div>
          )}

          {activeTab === "evidence" && (
            <>
              <div {...getRootProps()} className={`attestation-zone ${isDragActive ? "drag-active" : ""}`}>
                <input {...getInputProps()} />
                <p>{isDragActive ? "📄 Drop the PDF here..." : "📎 Drag PDF evidence (FBI/DOJ report, court doc) or click"}</p>
                <select value={sourceType} onChange={(e) => setSourceType(e.target.value)} onClick={(e) => e.stopPropagation()}>
                  <option value="DOJ_FBI">DOJ / FBI</option>
                  <option value="Court_Document">Court Document</option>
                  <option value="ZachXBT">ZachXBT Research</option>
                  <option value="News">News Report</option>
                </select>
                <button disabled={attesting}>{attesting ? "Attaching..." : "Attach Evidence"}</button>
              </div>
              <div className="evidence-list">
                <h4>Attached Evidence</h4>
                {attachedEvidence.length > 0 ? attachedEvidence.map((e, i) => (<div key={i} className="evidence-item"><p><strong>{e.source_type}</strong></p><p className="hash">{e.hash.substring(0, 16)}...</p></div>)) : <p>No evidence attached yet</p>}
              </div>
            </>
          )}

          {activeTab === "narrative" && (
            <>
              <div className="action-buttons">
                <button onClick={generateNarrative} disabled={!graphData.nodes.length || narrativeLoading}>{narrativeLoading ? "Generating..." : "Generate AI Narrative"}</button>
                <button onClick={exportReport} disabled={!graphData.nodes.length || exportLoading}>{exportLoading ? "Exporting..." : "Export Case File"}</button>
              </div>
              <div className="investigation-notes">
                <h4>Investigator Notes</h4>
                <textarea value={investigationNotes} onChange={(e) => setInvestigationNotes(e.target.value)} placeholder="Add case notes..." rows={4} />
              </div>
              {narrative && <div className="narrative"><h4>AI Summary</h4><p>{narrative}</p></div>}
            </>
          )}
        </div>
      </div>

      <footer className="footer">
        <a href="/trust-charter">Trust Charter</a>
        <a href="https://github.com/evidencly/evidencly">GitHub</a>
        <span>© 2026 Evidencly</span>
      </footer>
    </div>
  );
}

export default App;
