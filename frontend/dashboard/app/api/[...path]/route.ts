import type { NextRequest } from "next/server";

const backendUrl =
  process.env.BOTTLENECK_API_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const target = new URL(`${backendUrl}/${path.join("/")}`);
  target.search = request.nextUrl.search;

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.text();
  const response = await fetch(target, {
    method: request.method,
    body,
    headers: {
      accept: request.headers.get("accept") ?? "application/json",
      "content-type": request.headers.get("content-type") ?? "application/json",
    },
    cache: "no-store",
  });

  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
