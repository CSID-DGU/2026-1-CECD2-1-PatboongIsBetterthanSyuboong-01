import { NextResponse } from "next/server";

const BACKEND_BASE_URL = process.env.BACKEND_API_BASE_URL ?? "http://localhost:8080";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const queryString = searchParams.toString();

  const upstreamUrl = `${BACKEND_BASE_URL}/api/diagnoses${queryString ? `?${queryString}` : ""}`;

  try {
    const headers = new Headers();
    headers.set("Accept", "application/json");

    const authHeader = request.headers.get("authorization");
    if (authHeader) {
      headers.set("Authorization", authHeader);
    }

    const cookieHeader = request.headers.get("cookie");
    if (cookieHeader) {
      headers.set("Cookie", cookieHeader);
    }

    const response = await fetch(upstreamUrl, {
      headers,
      cache: "no-store",
      credentials: "include",
    });

    if (!response.ok) {
      const message = await response.text();
      return NextResponse.json(
        {
          message: message || "Backend responded with an error.",
        },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to proxy diagnoses request", error);
    return NextResponse.json(
      { message: "Failed to contact backend service." },
      { status: 500 }
    );
  }
}


