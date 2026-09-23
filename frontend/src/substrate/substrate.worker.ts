import { SubstrateEngine } from "./engine";
import type { SubstrateIn, SubstrateOut } from "./protocol";

const engine = new SubstrateEngine((msg: SubstrateOut) => {
  self.postMessage(msg);
});

self.onmessage = (event: MessageEvent<SubstrateIn>) => {
  engine.handle(event.data);
};
