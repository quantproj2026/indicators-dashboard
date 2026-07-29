import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  apiBaseUrl,
  apiFetch,
  csvDownloadUrl,
  getOverview,
  getSeries,
} from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

// These run under jsdom, so `window` exists and `apiBaseUrl` takes its browser
// branch -- which is the one that matters here, because it decides the origin
// the user's browser will actually call.
describe("apiBaseUrl (browser)", () => {
  const original = { ...process.env };

  afterEach(() => {
    process.env = { ...original };
  });

  it("falls back to localhost when nothing is configured", () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    expect(apiBaseUrl()).toBe("http://localhost:8000");
  });

  it("uses the public base URL, since a private one is unreachable here", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com";
    process.env.API_BASE_URL = "http://backend.internal:8000";
    expect(apiBaseUrl()).toBe("https://api.example.com");
  });

  it("strips a trailing slash so paths never double up", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com/";
    expect(apiBaseUrl()).toBe("https://api.example.com");
  });
});

describe("apiFetch", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("targets the versioned API prefix", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await apiFetch("/indicators");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/indicators");
  });

  it("serialises query parameters and drops empty ones", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await apiFetch("/indicators/cpi", {
      params: { interval: "monthly", limit: 10, maturity: undefined, order: "" },
    });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("interval=monthly");
    expect(url).toContain("limit=10");
    expect(url).not.toContain("maturity");
    expect(url).not.toContain("order");
  });

  it("does not add a second cache layer over the backend's", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    await apiFetch("/meta");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ cache: "no-store" });
  });

  it("surfaces the backend's error code and message", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { error: { code: "upstream_rate_limited", message: "Daily limit reached." } },
        429,
      ),
    );

    await expect(apiFetch("/indicators/cpi")).rejects.toMatchObject({
      code: "upstream_rate_limited",
      status: 429,
      message: "Daily limit reached.",
    });
  });

  it("flags a rate limit whichever way the backend signals it", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ error: { code: "upstream_rate_limited", message: "x" } }, 429),
    );
    const error = await apiFetch("/indicators/cpi").catch((cause) => cause);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).isRateLimited).toBe(true);
  });

  it("reports a missing key distinctly, since that needs a config change", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ error: { code: "api_key_missing", message: "no key" } }, 500),
    );
    const error = (await apiFetch("/indicators/cpi").catch((c) => c)) as ApiError;
    expect(error.isMissingKey).toBe(true);
  });

  it("copes with an error body that is not JSON", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error("not json");
      },
    } as unknown as Response);

    await expect(apiFetch("/indicators/cpi")).rejects.toMatchObject({
      status: 502,
      code: "http_502",
    });
  });

  it("turns a dead connection into an actionable message", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    const error = (await apiFetch("/indicators").catch((c) => c)) as ApiError;
    expect(error.isOffline).toBe(true);
    expect(error.code).toBe("backend_unreachable");
    expect(error.message).toMatch(/FastAPI backend running/);
  });

  it("re-throws an abort rather than disguising it as a network failure", async () => {
    fetchMock.mockRejectedValue(new DOMException("aborted", "AbortError"));
    await expect(apiFetch("/indicators")).rejects.toThrow(DOMException);
  });
});

describe("endpoint helpers", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => vi.unstubAllGlobals());

  it("reads the overview from the batch endpoint", async () => {
    await getOverview();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/indicators/latest");
  });

  it("passes indicator parameters straight through", async () => {
    await getSeries("treasury-yield", { interval: "daily", maturity: "3month" });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/indicators/treasury-yield");
    expect(url).toContain("interval=daily");
    expect(url).toContain("maturity=3month");
  });
});

describe("csvDownloadUrl", () => {
  it("points at the backend's CSV passthrough", () => {
    const url = csvDownloadUrl("cpi", { interval: "semiannual" });
    expect(url).toContain("/api/v1/indicators/cpi");
    expect(url).toContain("datatype=csv");
    expect(url).toContain("interval=semiannual");
  });

  it("never carries anything resembling a key", () => {
    expect(csvDownloadUrl("cpi")).not.toContain("apikey");
  });
});
