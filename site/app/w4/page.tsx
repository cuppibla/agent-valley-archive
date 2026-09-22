"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import FamiliarPicker from "@/components/FamiliarPicker";
import SaveChip from "@/components/SaveChip";
import Tower, { type Floors } from "@/components/Tower";
import Written from "@/components/Written";
import { getSave, updateSave, type SaveFile } from "@/lib/save";

/** The Archive — one building, and the visitor climbing it.
 *
 * Left, you are the visitor and you talk to Vesper at the desk on the ground
 * floor. Right, the tower: what she has written down, stacked by how far it
 * reaches. Chapter by chapter a floor lights up, and the thing that lights it
 * is a line you edited in `archive/`.
 *
 * Three buttons, and that is all: 🌙 ends the day, 🗓 starts the next visit,
 * 🔥 forgets you. Everything else this page does, it does by reading — the
 * service re-reads your code on every message, and the tower redraws.
 */

type Bubble = { who: "me" | "v" | "sys"; text: string; k: number };
type Progress = {
  session_store: string; memory_store: string; case_key: string;
  state_write: boolean; recall_reads: boolean;
  file_writes: boolean; has_written: number; topics: string[] | null;
  season: string; level: number; error: string | null;
};

const SID_KEY = "a101.w4.sid";
const newSid = () => "v-" + Math.random().toString(36).slice(2, 10);

export default function Archive() {
  const [save, setSave] = useState<SaveFile | null | undefined>(undefined);
  const [chat, setChat] = useState<Bubble[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [down, setDown] = useState(false);
  const [floors, setFloors] = useState<Floors | null>(null);
  const [prog, setProg] = useState<Progress | null>(null);
  const [rising, setRising] = useState<string[] | null>(null);
  const sid = useRef(""); const k = useRef(0); const box = useRef<HTMLDivElement>(null);
  const busyRef = useRef(false);

  const say = (who: Bubble["who"], t: string) =>
    setChat((c) => [...c, { who, text: t, k: k.current++ }]);

  useEffect(() => { setSave(getSave()); }, []);
  useEffect(() => {
    const el = box.current; if (el) el.scrollTop = el.scrollHeight;
  }, [chat, busy]);

  const restore = useCallback(async () => {
    if (!sid.current) return;
    const s = await fetch(`/api/w4/session/${sid.current}`).then((r) => r.json()).catch(() => null);
    if (!s || s.down) { setDown(true); return; }
    setDown(false);
    if (s.progress) setProg(s.progress);
    if (s.floors) setFloors(s.floors);
    const bs: Bubble[] = [];
    for (const e of (s.events ?? []) as { author: string; node: string; text: string }[]) {
      if (e.author === "user") { if (!e.text.startsWith("[")) bs.push({ who: "me", text: e.text, k: k.current++ }); }
      else if (["vesper", "goodnight"].includes(e.node))
        bs.push({ who: "v", text: e.text, k: k.current++ });
    }
    setChat(bs);
  }, []);

  // The service re-reads your code on every message, but you also edit between
  // messages — so the tower asks again whenever the window comes back.
  const poll = useCallback(async () => {
    const p = await fetch("/api/w4/progress").then((r) => r.json()).catch(() => null);
    if (p && !p.down) { setProg(p); setDown(false); restore(); } else setDown(true);
  }, [restore]);

  useEffect(() => {
    sid.current = localStorage.getItem(SID_KEY) || "";
    if (!sid.current) { sid.current = newSid(); localStorage.setItem(SID_KEY, sid.current); }
    poll();
    const back = () => { if (document.visibilityState === "visible") poll(); };
    document.addEventListener("visibilitychange", back);
    window.addEventListener("focus", back);
    return () => { document.removeEventListener("visibilitychange", back); window.removeEventListener("focus", back); };
  }, [poll]);

  // Shut for the night: when the process is gone (Ctrl+C in tab 3) the tower
  // goes dark and keeps knocking until `bash valley.sh` opens it again.
  useEffect(() => {
    if (!down) return;
    const t = setInterval(poll, 1500);
    return () => clearInterval(t);
  }, [down, poll]);

  // The Archive stamp, like week three's: yours once floor three is lit by a
  // tower that outlives the process.
  useEffect(() => {
    if (save && prog && prog.level >= 3 && !save.stamps[3]) {
      const stamps = [...save.stamps]; stamps[3] = true;
      setSave(updateSave({ stamps }));
    }
  }, [prog, save]);

  async function consume(res: Response) {
    const reader = res.body?.getReader(); if (!reader) { setDown(true); return; }
    const dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { done, value } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      const chunks = buf.split("\n\n"); buf = chunks.pop() ?? "";
      for (const c of chunks) {
        if (!c.startsWith("data: ")) continue;
        const d = JSON.parse(c.slice(6));
        if (d.kind === "progress") setProg(d);
        else if (d.kind === "node") {
          if ((d.node === "vesper" || d.node === "goodnight") && d.text) say("v", d.text);
        } else if (d.kind === "state") {
          setFloors(d.floors);
          if (d.progress) setProg(d.progress);
        } else if (d.kind === "error") say("sys", d.message);
        else if (d.kind === "down") { setDown(true); return; }
      }
    }
  }

  async function send(t: string) {
    const msg = t.trim(); if (!msg || busyRef.current || down) return;
    setBusy(true); busyRef.current = true; setText(""); say("me", msg);
    const res = await fetch("/api/w4/chat", { method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ session_id: sid.current, text: msg }) }).catch(() => null);
    if (res) await consume(res); else setDown(true);
    setBusy(false); busyRef.current = false;
  }

  async function closeDay() {
    if (busyRef.current || down) return;
    setBusy(true); busyRef.current = true;
    say("me", "🌙 that's all for today");
    // what you said today, lifting off the desk
    const mine = chat.filter((b) => b.who === "me" && !b.text.startsWith("🌙")).slice(-3);
    setRising(mine.map((b) => b.text.slice(0, 26) + (b.text.length > 26 ? "…" : "")));
    setTimeout(() => setRising(null), 2600);
    const res = await fetch("/api/w4/close", { method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ session_id: sid.current }) }).catch(() => null);
    if (res) await consume(res); else setDown(true);
    setBusy(false); busyRef.current = false;
  }

  function monthLater() {
    sid.current = newSid(); localStorage.setItem(SID_KEY, sid.current);
    setChat([]);
    say("sys", "🗓 a month later — a brand-new visit, same visitor");
    poll();
  }

  async function forget() {
    if (!window.confirm("Forget everything about this visitor?\n\nFloor three empties and the drawer clears. Floor one keeps its books — those are the record, not the memory.")) return;
    await fetch("/api/w4/forget", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ session_id: sid.current }) }).catch(() => null);
    say("sys", "🔥 forgotten — floor one still has its books");
    restore();
  }

  if (save === undefined) return null;
  if (!save?.name) return <FamiliarPicker onDone={() => setSave(getSave())} />;

  const status = down ? "shut for the night" : busy ? "looking it up" : "at the desk";
  const dot = down ? "#6b6394" : busy ? "var(--violet)" : "var(--mint)";

  return (
    <div className="wrap" style={{ maxWidth: 1340, paddingBottom: 30 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end",
        marginBottom: 14, gap: 16 }}>
        <div>
          <div className="eyebrow">04 · REMEMBER</div>
          <h1 className="serif" style={{ fontWeight: 500, fontSize: 30, margin: "4px 0 0" }}>The Archive</h1>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {prog?.error && <span className="mono" style={{ fontSize: 11, color: "var(--gold-deep)",
            background: "rgba(230,192,105,.18)", padding: "6px 12px", borderRadius: 10,
            maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
            title={prog.error}>⚠ {prog.error}</span>}
          <Link href="/" className="mono" style={{ fontSize: 11.5, padding: "7px 12px", borderRadius: 999,
            border: "1px solid var(--line)", background: "rgba(255,255,255,.55)", color: "var(--violet)" }}>map</Link>
          <SaveChip />
        </div>
      </div>

      <div data-shot="both" style={{ display: "grid", gridTemplateColumns: "440px 1fr", gap: 18,
        alignItems: "stretch" }}>

        {/* ── the desk ─────────────────────────────────────── */}
        <section className="glass" data-shot="desk"
          style={{ display: "flex", flexDirection: "column", padding: "18px 18px 14px" }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center", paddingBottom: 13,
            borderBottom: "1px solid var(--line)" }}>
            <img src="/world/npc/vesper.jpg" alt="Vesper" width={80} height={80}
              style={{ width: 80, height: 80, borderRadius: 20, objectFit: "cover",
                border: "3px solid var(--gold)", boxShadow: "0 6px 18px rgba(185,138,46,.25)",
                filter: down ? "saturate(.3) brightness(.85)" : "none", transition: "filter .8s" }} />
            <div>
              <div className="serif" style={{ fontSize: 21, fontWeight: 600 }}>Vesper</div>
              <div className="eyebrow" style={{ fontSize: 10, marginTop: 2 }}>the Archivist</div>
              <div className="mono" style={{ display: "inline-flex", alignItems: "center", gap: 7,
                fontSize: 11, padding: "5px 11px", borderRadius: 999, background: "#fff",
                border: "1px solid var(--line)", color: "var(--sub)", marginTop: 7 }}>
                <i style={{ width: 8, height: 8, borderRadius: "50%", background: dot,
                  boxShadow: `0 0 0 3px ${dot}33`, display: "inline-block" }} />
                {status}
              </div>
            </div>
          </div>

          <div ref={box} style={{ flex: 1, minHeight: 300, maxHeight: 460, overflowY: "auto",
            display: "flex", flexDirection: "column", gap: 10, padding: "14px 2px 8px" }}>
            {chat.length === 0 && (
              <div style={bubble("v")}>Welcome to the Archive. How can I help you today?</div>
            )}
            {chat.map((b) => b.who === "sys"
              ? <div key={b.k} className="mono" style={{ alignSelf: "center", fontSize: 11,
                  color: "var(--faint)", padding: "2px 8px", textAlign: "center" }}>{b.text}</div>
              : <div key={b.k} style={bubble(b.who)}>{b.text}</div>)}
            {busy && <div className="mono" style={{ fontSize: 11.5, color: "var(--gold-deep)", padding: 4 }}>
              Vesper is looking it up…</div>}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 8px 8px 10px",
            borderRadius: 18, background: "#fff", border: "1px solid var(--line)" }}>
            <img src={save.portrait} alt={save.name} width={40} height={40}
              style={{ width: 40, height: 40, borderRadius: "50%", objectFit: "cover",
                border: "2px solid var(--gold)" }} />
            <input value={text} disabled={busy || down} onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(text); }}
              placeholder={down ? "the Archive is shut…" : "Talk to Vesper…"}
              style={{ flex: 1, border: "none", outline: "none", fontSize: 14.5,
                background: "transparent", color: "var(--ink)" }} />
            <button onClick={() => send(text)} disabled={busy || down || !text.trim()}
              style={{ width: 36, height: 36, borderRadius: "50%", border: "none", color: "#fff",
                fontSize: 16, background: "linear-gradient(180deg,var(--violet-soft),var(--violet))",
                opacity: busy || down || !text.trim() ? .45 : 1 }}>↑</button>
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center",
            marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
            <button className="rune on" disabled={busy || down} onClick={closeDay}
              style={{ opacity: busy || down ? .5 : 1 }}
              title="closing time — she walks back past the shelves">🌙 that&apos;s all for today</button>
            <button onClick={monthLater} style={btn("ok")}
              title="a new visit — same visitor, same tower">🗓 a month later</button>
            <button onClick={forget} style={btn("no")}
              title="floor three empties, the drawer clears, floor one keeps its books">🔥 forget me</button>
          </div>
        </section>

        {/* ── the tower ────────────────────────────────────── */}
        <section className="glass" style={{ padding: "16px 20px" }}>
          <div data-shot="tower-side" style={{ display: "grid", gridTemplateColumns: "292px 1fr",
            gap: 16, alignItems: "start" }}>
            <Tower floors={floors} level={prog?.level ?? 0} dark={down} rising={rising}
              familiar={save.portrait || "/world/icons/species/cat.jpg"} name={save.name} />
            <Written floors={floors} name={save.name} />
          </div>
        </section>
      </div>
    </div>
  );
}

function bubble(who: "me" | "v"): React.CSSProperties {
  return who === "me"
    ? { alignSelf: "flex-end", maxWidth: "86%", padding: "10px 13px", borderRadius: 18,
        borderBottomRightRadius: 6, fontSize: 14, lineHeight: 1.45, color: "#fff",
        background: "linear-gradient(180deg,var(--violet-soft),var(--violet))",
        animation: "riseIn .25s ease both" }
    : { alignSelf: "flex-start", maxWidth: "88%", padding: "10px 13px", borderRadius: 18,
        borderBottomLeftRadius: 6, fontSize: 14, lineHeight: 1.45, color: "var(--ink)",
        background: "#fff", border: "1px solid var(--line)", animation: "riseIn .25s ease both" };
}
function btn(kind: "ok" | "no"): React.CSSProperties {
  if (kind === "ok") return { fontSize: 12, fontWeight: 600, padding: "9px 13px", borderRadius: 14,
    border: "none", color: "#fff", whiteSpace: "nowrap",
    background: "linear-gradient(180deg,#8ad6bd,#5fb99c)", boxShadow: "0 6px 16px rgba(111,199,173,.35)" };
  return { fontSize: 12, fontWeight: 600, padding: "9px 13px", borderRadius: 14,
    border: "1.5px solid var(--rose)", color: "#b03e64", background: "#fff", whiteSpace: "nowrap" };
}
