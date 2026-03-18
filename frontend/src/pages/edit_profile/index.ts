import { mount } from "svelte";
import EditProfilePage from "./EditProfilePage.svelte";

const app = mount(EditProfilePage, {
  target: document.getElementById("app-root")!,
});

export default app;
