import { json } from "../_proxy";
export const dynamic = "force-dynamic";
export async function POST(req: Request) {
  return json("/forget", { method: "POST", headers: { "content-type": "application/json" }, body: await req.text() });
}
