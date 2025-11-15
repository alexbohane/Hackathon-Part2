import { useEffect, useState } from "react";
import clsx from "clsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChatKitPanel } from "./ChatKitPanel";
import { FactCard } from "./FactCard";
import { ThemeToggle } from "./ThemeToggle";
import { ColorScheme } from "../hooks/useColorScheme";
import { useFacts } from "../hooks/useFacts";

type Tab = "plan" | "execute";

export default function Home({
  scheme,
  handleThemeChange,
}: {
  scheme: ColorScheme;
  handleThemeChange: (scheme: ColorScheme) => void;
}) {
  const { facts, refresh, performAction } = useFacts();
  const [activeTab, setActiveTab] = useState<Tab>("plan");
  const [summary, setSummary] = useState<string | null>(null);
  const [posterUrl, setPosterUrl] = useState<string | null>(null);
  const [eventName, setEventName] = useState<string | null>(null);
  const [hackathonRules, setHackathonRules] = useState<string | null>(null);
  const [showRules, setShowRules] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // Checklist state
  const [step1Complete, setStep1Complete] = useState(false);
  const [step2Complete, setStep2Complete] = useState(false);
  const [step3Complete, setStep3Complete] = useState(false);

  const containerClass = clsx(
    "min-h-screen transition-colors duration-300 relative overflow-hidden",
    scheme === "dark"
      ? "bg-gradient-to-br from-slate-900 via-slate-950 to-slate-850 text-slate-100"
      : "bg-gradient-to-br from-blue-50 via-sky-50 to-cyan-50 text-slate-900"
  );

  const formatFactsAsMarkdown = () => {
    if (facts.length === 0) {
      return "# Event Details\n\nNo event details have been saved yet.";
    }

    return `# Event Details\n\n${facts.map((fact, index) => `${index + 1}. ${fact.text}`).join("\n")}`;
  };

  const fetchSummary = async () => {
    const markdown = formatFactsAsMarkdown();
    if (facts.length === 0) {
      setSummary(null);
      setPosterUrl(null);
      setEventName(null);
      setHackathonRules(null);
      return;
    }

    setIsSummarizing(true);
    setSummaryError(null);

    // Reset checklist
    setStep1Complete(false);
    setStep2Complete(false);
    setStep3Complete(false);
    setShowRules(false);

    try {
      // Step 1: Calling Potential Venues (5 second timer)
      await new Promise(resolve => setTimeout(resolve, 5000));
      setStep1Complete(true);

      // Step 2 & 3: Generate poster and rules (happens together in the API)
      const response = await fetch("/summarize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ markdown }),
      });

      if (!response.ok) {
        throw new Error(`Failed to summarize: ${response.statusText}`);
      }

      const data = await response.json();
      setSummary(data.summary);
      setPosterUrl(data.poster_url || null);
      setEventName(data.event_name || null);
      setHackathonRules(data.hackathon_rules || null);

      // Mark steps as complete
      setStep2Complete(true);
      if (data.hackathon_rules) {
        setStep3Complete(true);
      }
    } catch (error) {
      console.error("Error summarizing:", error);
      setSummaryError(error instanceof Error ? error.message : "Failed to generate summary");
    } finally {
      setIsSummarizing(false);
    }
  };

  // Removed automatic generation - user must click "Generate Poster" button

  return (
    <div className={containerClass}>
      {/* Decorative Background Motifs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-[0.03]">
        <div className="absolute top-20 left-10 w-96 h-96 bg-blue-400 rounded-full blur-3xl"></div>
        <div className="absolute top-40 right-20 w-80 h-80 bg-cyan-400 rounded-full blur-3xl"></div>
        <div className="absolute bottom-20 left-1/3 w-72 h-72 bg-sky-400 rounded-full blur-3xl"></div>
        <div className="absolute bottom-40 right-1/4 w-64 h-64 bg-indigo-300 rounded-full blur-3xl"></div>

        {/* Geometric patterns */}
        <svg className="absolute top-0 left-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-blue-200"/>
            </pattern>
            <pattern id="dots" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="20" cy="20" r="1" fill="currentColor" className="text-blue-200"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
          <rect width="100%" height="100%" fill="url(#dots)" opacity="0.5" />
        </svg>
      </div>

      <div className="relative z-10 mx-auto min-h-screen w-full max-w-6xl px-6 pt-4 pb-10 md:py-10">
        {/* Tab Navigation */}
        <div className="mb-8 flex items-center justify-between gap-4">
          <div className="flex gap-2 rounded-xl bg-white/70 p-1.5 shadow-lg backdrop-blur-sm dark:bg-slate-900/70">
            <button
              onClick={() => setActiveTab("plan")}
              className={clsx(
                "rounded-lg px-6 py-2.5 text-sm font-semibold transition-all duration-200",
                activeTab === "plan"
                  ? "bg-slate-900 text-white shadow-md dark:bg-slate-100 dark:text-slate-900"
                  : "text-slate-600 hover:bg-slate-100/50 dark:text-slate-300 dark:hover:bg-slate-800/50"
              )}
            >
              Plan Event
            </button>
            <button
              onClick={() => setActiveTab("execute")}
              className={clsx(
                "rounded-lg px-6 py-2.5 text-sm font-semibold transition-all duration-200",
                activeTab === "execute"
                  ? "bg-slate-900 text-white shadow-md dark:bg-slate-100 dark:text-slate-900"
                  : "text-slate-600 hover:bg-slate-100/50 dark:text-slate-300 dark:hover:bg-slate-800/50"
              )}
            >
              Execute
            </button>
          </div>
          <ThemeToggle value={scheme} onChange={handleThemeChange} />
        </div>

        {/* Tab Content */}
        {activeTab === "plan" ? (
          <div className="relative">
            <div className="flex flex-col-reverse gap-10 lg:flex-row">
              <div className="w-full md:w-[45%] flex h-[70vh] items-stretch overflow-hidden rounded-3xl bg-white/80 shadow-[0_45px_90px_-45px_rgba(15,23,42,0.6)] ring-1 ring-slate-200/60 backdrop-blur dark:bg-slate-900/70 dark:shadow-[0_45px_90px_-45px_rgba(15,23,42,0.85)] dark:ring-slate-800/60">
                <ChatKitPanel
                  theme={scheme}
                  onWidgetAction={performAction}
                  onResponseEnd={refresh}
                  onThemeRequest={handleThemeChange}
                />
              </div>
              <section className="flex-1 space-y-8 py-8">
                <header className="space-y-6">
                  <div className="space-y-3">
                    <h1 className="text-3xl font-semibold sm:text-4xl">
                      Event Planner
                    </h1>
                    <p className="max-w-xl text-sm text-slate-600 dark:text-slate-300">
                      Your event details are saved automatically as you share them in the conversation.
                      All information about your event will appear here on the right side.
                    </p>
                  </div>
                </header>

                <div>
                  <h2 className="text-lg font-semibold text-slate-700 dark:text-slate-200">
                    Event Details
                  </h2>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Event details appear here automatically as you share them in the conversation.
                  </p>
                  <div className="mt-6">
                    <div className="rounded-3xl border border-slate-200/60 bg-white/70 shadow-[0_35px_90px_-55px_rgba(15,23,42,0.45)] ring-1 ring-slate-200/50 backdrop-blur-sm dark:border-slate-800/70 dark:bg-slate-900/50 dark:shadow-[0_45px_95px_-60px_rgba(15,23,42,0.85)] dark:ring-slate-900/60">
                      <div className="max-h-[50vh] overflow-y-auto p-6 sm:max-h-[40vh]">
                        {facts.length === 0 ? (
                          <div className="flex flex-col items-start justify-center gap-3 text-slate-600 dark:text-slate-300">
                            <span className="text-base font-medium text-slate-700 dark:text-slate-200">
                              No event details saved yet.
                            </span>
                            <span className="text-sm text-slate-500 dark:text-slate-400">
                              Start a conversation in the chat to record your event details.
                            </span>
                          </div>
                        ) : (
                          <ul className="list-none space-y-3">
                            {facts.map((fact) => (
                              <FactCard key={fact.id} fact={fact} />
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </div>
        ) : (
          <div className="min-h-[90vh] relative">
            <div className="rounded-3xl border border-slate-200/60 bg-white/80 shadow-[0_45px_90px_-45px_rgba(15,23,42,0.6)] ring-1 ring-slate-200/60 backdrop-blur dark:border-slate-800/70 dark:bg-slate-900/70 dark:shadow-[0_45px_90px_-45px_rgba(15,23,42,0.85)] dark:ring-slate-800/60">
              <div className="overflow-y-auto p-8">
                {facts.length === 0 ? (
                  <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-slate-600 dark:text-slate-300">
                    <span className="text-base font-medium text-slate-700 dark:text-slate-200">
                      No event details saved yet.
                    </span>
                    <span className="text-sm text-slate-500 dark:text-slate-400">
                      Go to the Plan Event tab to add event details first.
                    </span>
                  </div>
                ) : !summary && !isSummarizing && !summaryError ? (
                  <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
                    <div className="text-center space-y-3">
                      <h2 className="text-2xl font-semibold text-slate-700 dark:text-slate-200">
                        Ready to Generate Materials
                      </h2>
                      <p className="text-slate-600 dark:text-slate-300 max-w-md">
                        Click the button below to call venues and generate summary, poster, and rules for your event.
                      </p>
                    </div>
                    <button
                      onClick={fetchSummary}
                      disabled={facts.length === 0}
                      className={clsx(
                        "rounded-xl px-8 py-4 text-base font-semibold shadow-lg transition-all duration-200",
                        facts.length === 0
                          ? "cursor-not-allowed bg-slate-300 text-slate-500 dark:bg-slate-700 dark:text-slate-400"
                          : "bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700 hover:shadow-xl active:scale-95"
                      )}
                    >
                      Call Venue and Generate Material
                    </button>
                  </div>
                ) : isSummarizing ? (
                  <div className="flex flex-col items-start min-h-[60vh] gap-6 py-8">
                    <h2 className="text-2xl font-semibold text-slate-700 dark:text-slate-200">
                      Generating Event Materials
                    </h2>
                    <div className="space-y-4 w-full">
                      {/* Step 1: Calling Potential Venues */}
                      <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                        <div className={clsx(
                          "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300",
                          step1Complete
                            ? "bg-green-500"
                            : "bg-blue-600"
                        )}>
                          {step1Complete ? (
                            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          ) : (
                            <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
                          )}
                        </div>
                        <div className="flex-1">
                          <h3 className={clsx(
                            "font-semibold mb-1",
                            step1Complete
                              ? "text-green-700 dark:text-green-400"
                              : "text-slate-700 dark:text-slate-200"
                          )}>
                            1. Calling Potential Venues
                          </h3>
                          {!step1Complete && (
                            <p className="text-sm text-slate-600 dark:text-slate-400">
                              Contacting venues...
                            </p>
                          )}
                          {step1Complete && (
                            <p className="text-sm text-green-600 dark:text-green-400">
                              Venues contacted successfully
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Step 2: Generate Poster */}
                      <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                        <div className={clsx(
                          "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300",
                          step2Complete
                            ? "bg-green-500"
                            : step1Complete
                            ? "bg-blue-600"
                            : "bg-slate-300 dark:bg-slate-600"
                        )}>
                          {step2Complete ? (
                            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          ) : step1Complete ? (
                            <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent"></div>
                          ) : (
                            <div className="w-2 h-2 bg-slate-400 rounded-full"></div>
                          )}
                        </div>
                        <div className="flex-1">
                          <h3 className={clsx(
                            "font-semibold mb-1",
                            step2Complete
                              ? "text-green-700 dark:text-green-400"
                              : step1Complete
                              ? "text-slate-700 dark:text-slate-200"
                              : "text-slate-500 dark:text-slate-400"
                          )}>
                            2. Generate Poster
                          </h3>
                          {!step2Complete && step1Complete && (
                            <p className="text-sm text-slate-600 dark:text-slate-400">
                              Creating poster design...
                            </p>
                          )}
                          {step2Complete && (
                            <p className="text-sm text-green-600 dark:text-green-400">
                              Poster generated successfully
                            </p>
                          )}
                          {!step1Complete && (
                            <p className="text-sm text-slate-500 dark:text-slate-500">
                              Waiting for step 1...
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Step 3: Generate Hackathon Rules */}
                      <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                        <div className={clsx(
                          "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300",
                          step3Complete
                            ? "bg-green-500"
                            : step2Complete
                            ? "bg-blue-600"
                            : "bg-slate-300 dark:bg-slate-600"
                        )}>
                          {step3Complete ? (
                            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          ) : step2Complete ? (
                            <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent"></div>
                          ) : (
                            <div className="w-2 h-2 bg-slate-400 rounded-full"></div>
                          )}
                        </div>
                        <div className="flex-1">
                          <h3 className={clsx(
                            "font-semibold mb-1",
                            step3Complete
                              ? "text-green-700 dark:text-green-400"
                              : step2Complete
                              ? "text-slate-700 dark:text-slate-200"
                              : "text-slate-500 dark:text-slate-400"
                          )}>
                            3. Generate Hackathon Rules
                          </h3>
                          {!step3Complete && step2Complete && (
                            <p className="text-sm text-slate-600 dark:text-slate-400">
                              Creating rules document...
                            </p>
                          )}
                          {step3Complete && (
                            <p className="text-sm text-green-600 dark:text-green-400">
                              Rules generated successfully
                            </p>
                          )}
                          {!step2Complete && (
                            <p className="text-sm text-slate-500 dark:text-slate-500">
                              Waiting for step 2...
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : summaryError ? (
                  <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                    <p className="text-red-600 dark:text-red-400 font-medium">
                      {summaryError}
                    </p>
                    <button
                      onClick={fetchSummary}
                      className="rounded-xl px-6 py-3 text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                    >
                      Retry
                    </button>
                  </div>
                ) : summary ? (
                  <div className="space-y-6">
                    <h2 className="text-2xl font-semibold text-slate-700 dark:text-slate-200">
                      Event Summary
                    </h2>
                    <div className="prose prose-slate dark:prose-invert max-w-none prose-headings:text-slate-700 dark:prose-headings:text-slate-200 prose-p:text-slate-700 dark:prose-p:text-slate-200 prose-strong:text-slate-900 dark:prose-strong:text-slate-100 prose-ul:text-slate-700 dark:prose-ul:text-slate-200 prose-ol:text-slate-700 dark:prose-ol:text-slate-200">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {summary}
                      </ReactMarkdown>
                    </div>
                    {posterUrl && (
                      <div className="space-y-3">
                        <h3 className="text-xl font-semibold text-slate-700 dark:text-slate-200">
                          {eventName ? `Event Poster: ${eventName}` : "Event Poster"}
                        </h3>
                        <div className="rounded-2xl overflow-hidden shadow-lg ring-1 ring-slate-200/60 dark:ring-slate-800/60">
                          <img
                            src={posterUrl}
                            alt={eventName || "Event poster"}
                            className="w-full h-auto"
                            onError={(e) => {
                              console.error("Failed to load poster image:", posterUrl);
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        </div>
                        <a
                          href={posterUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 transition-colors"
                        >
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                            />
                          </svg>
                          Open poster in new tab
                        </a>
                      </div>
                    )}
                    {hackathonRules && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h3 className="text-xl font-semibold text-slate-700 dark:text-slate-200">
                            Hackathon Rules
                          </h3>
                          <button
                            onClick={() => setShowRules(!showRules)}
                            className="rounded-lg px-4 py-2 text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                          >
                            {showRules ? "Hide Rules" : "Show Rules"}
                          </button>
                        </div>
                        {showRules && (
                          <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 max-h-[70vh] overflow-y-auto">
                            <div className="prose prose-slate dark:prose-invert max-w-none prose-headings:text-slate-700 dark:prose-headings:text-slate-200 prose-p:text-slate-700 dark:prose-p:text-slate-200 prose-strong:text-slate-900 dark:prose-strong:text-slate-100 prose-ul:text-slate-700 dark:prose-ul:text-slate-200 prose-ol:text-slate-700 dark:prose-ol:text-slate-200 prose-li:text-slate-700 dark:prose-li:text-slate-200">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {hackathonRules}
                              </ReactMarkdown>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    <button
                      onClick={fetchSummary}
                      className="mt-4 rounded-xl px-4 py-2 text-sm font-semibold bg-slate-200 text-slate-700 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600 transition-colors"
                    >
                      Call Venue and Regenerate Material
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
