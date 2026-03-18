import { mount } from "svelte";
import ProfilePage from "./ProfilePage.svelte";

const app = mount(ProfilePage, {
  target: document.getElementById("app-root")!,
});

export default app;
