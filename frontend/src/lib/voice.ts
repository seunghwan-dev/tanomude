const SPOKEN = new Set<string>();

let muted = false;
let selectedVoice: SpeechSynthesisVoice | null = null;
let voiceResolved = false;

function engine(): SpeechSynthesis | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    return null;
  }
  return window.speechSynthesis;
}

function resolveVoice(synth: SpeechSynthesis): void {
  if (voiceResolved) {
    return;
  }
  const voices = synth.getVoices();
  if (voices.length === 0) {
    return;
  }
  selectedVoice =
    voices.find((voice) => voice.lang === "ja-JP") ??
    voices.find((voice) => voice.lang.toLowerCase().startsWith("ja")) ??
    null;
  voiceResolved = true;
}

const boot = engine();
if (boot) {
  resolveVoice(boot);
  if (!voiceResolved) {
    boot.addEventListener("voiceschanged", () => resolveVoice(boot), { once: true });
  }
}

export function isVoiceSupported(): boolean {
  return engine() !== null;
}

export function setVoiceMuted(value: boolean): void {
  muted = value;
  if (value) {
    engine()?.cancel();
  }
}

function speakOnce(key: string, text: string): void {
  if (SPOKEN.has(key)) {
    return;
  }
  if (muted) {
    return;
  }
  const synth = engine();
  if (synth === null) {
    return;
  }
  resolveVoice(synth);
  try {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ja-JP";
    if (selectedVoice !== null) {
      utterance.voice = selectedVoice;
    }
    synth.speak(utterance);
    SPOKEN.add(key);
  } catch {
    SPOKEN.add(key);
  }
}

export function voicePlanReady(taskId: number): void {
  speakOnce(`task:${taskId}:plan-ready`, "計画案ができました。ご確認のうえ、承認をお願いいたします。");
}

export function voicePlanRefused(taskId: number): void {
  speakOnce(
    `task:${taskId}:plan-refused`,
    "申し訳ありません。入力内容に不備があり、この申請は実行できません。ご確認をお願いいたします。",
  );
}

export function voicePlanUnreadable(taskId: number): void {
  speakOnce(`task:${taskId}:plan-unreadable`, "申し訳ありません。指示の解析に失敗し、計画を作成できませんでした。");
}

export function voiceOutcome(taskId: number, tripId: number | null, badData: boolean): void {
  const key = `task:${taskId}:outcome`;
  if (tripId !== null) {
    speakOnce(key, `送信が完了しました。出張番号は${tripId}番です。`);
    return;
  }
  if (badData) {
    speakOnce(
      key,
      "不正なデータを検知したため、処理を中止しました。育成候補として、次回の個人修正に活かします。",
    );
    return;
  }
  speakOnce(key, "再試行を尽くしましたが、画面状態が整合せず、処理を差し戻しました。要調査の案件です。");
}
