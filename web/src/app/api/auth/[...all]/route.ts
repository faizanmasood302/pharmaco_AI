import { auth } from "@/lib/auth";
import { NextRequest } from "next/server";

export const GET = async (request: NextRequest) => {
    return auth.handler(request);
};

export const POST = async (request: NextRequest) => {
    return auth.handler(request);
};
