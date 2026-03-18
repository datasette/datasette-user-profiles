import { mount } from "svelte";
import ProfilesPage from "./ProfilesPage.svelte";

const app = mount(ProfilesPage, {
  target: document.getElementById("app-root")!,
});

export default app;
