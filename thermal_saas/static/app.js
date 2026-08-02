const state = {
  profiles: [],
  profileId: "",
  questionnaire: null,
  organization: null,
  project: null,
  rooms: [],
  thermalLinks: [],
  token: "",
  user: null,
  selectedOrganization: null,
  answersSaved: false,
  latestAnswers: null,
  simulationRuns: [],
  latestReportId: null,
  simulationStatus: "idle",
  pendingDemoAnswers: null,
  lastSimulationError: "",
  projectDraftOpen: false,
  authSubmitting: "",
  branding: null,
  brandingLogoUrl: "",
  brandingEditorOpen: false,
};

const els = {
  email: document.querySelector("#email"),
  password: document.querySelector("#password"),
  login: document.querySelector("#login"),
  logout: document.querySelector("#logout"),
  authStatus: document.querySelector("#authStatus"),
  loggedOutAccount: document.querySelector("#loggedOutAccount"),
  loggedInAccount: document.querySelector("#loggedInAccount"),
  connectedEmail: document.querySelector("#connectedEmail"),
  connectedProfile: document.querySelector("#connectedProfile"),
  profileSelect: document.querySelector("#profileSelect"),
  projectName: document.querySelector("#projectName"),
  customerName: document.querySelector("#customerName"),
  projectSelect: document.querySelector("#projectSelect"),
  newProject: document.querySelector("#newProject"),
  projectCreateFields: document.querySelector("#projectCreateFields"),
  createProject: document.querySelector("#createProject"),
  loadProject: document.querySelector("#loadProject"),
  emptyProjects: document.querySelector("#emptyProjects"),
  projectStatus: document.querySelector("#projectStatus"),
  progressSteps: document.querySelector("#progressSteps"),
  projectSummary: document.querySelector("#projectSummary"),
  questionnaireIntro: document.querySelector("#questionnaireIntro"),
  questionnaireForm: document.querySelector("#questionnaireForm"),
  saveAnswers: document.querySelector("#saveAnswers"),
  saveAnswersBottom: document.querySelector("#saveAnswersBottom"),
  saveIndicator: document.querySelector("#saveIndicator"),
  answersStatus: document.querySelector("#answersStatus"),
  addRoomMenuButton: document.querySelector("#addRoomMenuButton"),
  roomTypeMenu: document.querySelector("#roomTypeMenu"),
  rooms: document.querySelector("#rooms"),
  runSimulation: document.querySelector("#runSimulation"),
  simulationState: document.querySelector("#simulationState"),
  simulationRuns: document.querySelector("#simulationRuns"),
  resultSummary: document.querySelector("#resultSummary"),
  brandingSection: document.querySelector("#brandingSection"),
  brandingSummary: document.querySelector("#brandingSummary"),
  brandingForm: document.querySelector("#brandingForm"),
  brandingLogo: document.querySelector("#brandingLogo"),
  brandingLogoPreview: document.querySelector("#brandingLogoPreview"),
  brandingColorPicker: document.querySelector("#brandingColorPicker"),
  brandingPrimaryColor: document.querySelector("#brandingPrimaryColor"),
  brandingPhone: document.querySelector("#brandingPhone"),
  brandingEmail: document.querySelector("#brandingEmail"),
  brandingWebsite: document.querySelector("#brandingWebsite"),
  brandingLegalMention: document.querySelector("#brandingLegalMention"),
  saveBranding: document.querySelector("#saveBranding"),
  skipBranding: document.querySelector("#skipBranding"),
  brandingStatus: document.querySelector("#brandingStatus"),
};

const hiddenQuestionIds = new Set(["project_name", "rooms"]);
const defaultHeatingEnergyPrices = {
  electric_radiator: 0.25,
  gas_boiler_standard: 0.11,
  gas_boiler_condensing: 0.11,
  fuel_oil_boiler_standard: 0.13,
  wood_stove_standard: 0.07,
  air_air_heat_pump_standard: 0.25,
  air_water_heat_pump_standard: 0.25,
};

async function api(path, options = {}) {
  const headers = {"Content-Type": "application/json", ...(options.headers || {})};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, {
    headers,
    credentials: "same-origin",
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({detail: response.statusText}));
    throw new Error(toUserError(error.detail || response.statusText));
  }
  return response.json();
}

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
  element.classList.toggle("success", Boolean(message) && !isError);
}

function toUserError(message) {
  const text = String(message || "");
  const known = {
    "Authentication required.": "Sign in required.",
    "Invalid email or password.": "Invalid email or password.",
    "Password must contain at least 8 characters.": "Password must contain at least 8 characters.",
    "A user with this email already exists.": "An account already exists with this email.",
    "Unknown project.": "Project not found for your organization.",
    "Unknown simulation run.": "Simulation not found for your organization.",
    "No answers saved for project": "No answers saved for this project.",
    "Organization already exists with a different business profile.": "This organization already exists with another configuration.",
    "Unknown business profile.": "Unknown configuration.",
    "primary_color must be a hex color.": "The color must be hexadecimal, for example #1a5c3a.",
    "logo_url must be an image data URL.": "The logo must be a PNG, JPG, or SVG image.",
    "logo_url is too large.": "The logo is too large.",
  };
  for (const [source, target] of Object.entries(known)) {
    if (text.includes(source)) return target;
  }
  return text || "Something went wrong.";
}

function updateUiState() {
  const isLoggedIn = Boolean(state.user);
  els.loggedOutAccount.hidden = isLoggedIn;
  els.loggedInAccount.hidden = !isLoggedIn;
  els.connectedEmail.textContent = isLoggedIn ? state.user.email : "";
  els.connectedProfile.textContent = "";
  els.profileSelect.hidden = true;
  els.logout.disabled = !isLoggedIn;
  els.brandingSection.hidden = !isLoggedIn;
  els.saveBranding.disabled = !isLoggedIn;
  els.saveBranding.textContent = "Save";
  els.login.disabled = isLoggedIn || state.authSubmitting === "login";
  els.brandingForm.hidden = !state.brandingEditorOpen;
  els.skipBranding.hidden = true;

  if (!isLoggedIn) {
    els.projectSelect.hidden = true;
    els.emptyProjects.hidden = false;
    els.emptyProjects.textContent = "Create an account or sign in to access projects";
    els.loadProject.disabled = true;
  }

  els.projectCreateFields.hidden = !state.projectDraftOpen;
  els.createProject.disabled = !state.organization || !state.projectDraftOpen;
  setSaveAnswersDisabled(!state.project);
  els.runSimulation.disabled = !state.project || !state.answersSaved || state.simulationStatus === "loading";
  els.newProject.disabled = !state.organization;
  els.addRoomMenuButton.disabled = !state.project;
  if (!state.project) els.roomTypeMenu.hidden = true;

  els.saveIndicator.textContent = state.answersSaved ? "✓ Saved" : "● Not saved";
  els.saveIndicator.className = `saveIndicator ${state.answersSaved ? "saved" : "unsaved"}`;
  renderProgress();
  renderProjectSummary();
  renderSimulationState();
  renderBrandingSummary();
}

function setSaveAnswersDisabled(disabled) {
  els.saveAnswers.disabled = disabled;
  els.saveAnswersBottom.disabled = disabled;
}

async function loadProfiles() {
  const payload = await api("/business-profiles");
  state.profiles = payload.profiles;
  const defaultProfile = state.profiles.find((profile) => profile.id === "roof_insulation_seller") || state.profiles[0];
  els.profileSelect.innerHTML = defaultProfile
    ? `<option value="${defaultProfile.id}">${defaultProfile.label}</option>`
    : "";
  els.profileSelect.value = defaultProfile?.id || "";
  state.profileId = els.profileSelect.value;
  if (state.token) {
    await refreshSession();
  } else {
    await loadQuestionnaire();
  }
  updateUiState();
}

async function loadBranding() {
  if (!state.user) return;
  const payload = await api("/organization-branding");
  applyBranding(payload.branding || {});
}

function applyBranding(branding) {
  state.branding = branding;
  state.brandingLogoUrl = branding.logo_url || "";
  els.brandingPrimaryColor.value = branding.primary_color || "#1a5c3a";
  els.brandingColorPicker.value = /^#[0-9a-fA-F]{6}$/.test(els.brandingPrimaryColor.value)
    ? els.brandingPrimaryColor.value
    : "#1a5c3a";
  els.brandingPhone.value = branding.phone || "";
  els.brandingEmail.value = branding.email_contact || "";
  els.brandingWebsite.value = branding.website || "";
  els.brandingLegalMention.value = branding.legal_mention || "";
  renderLogoPreview();
  renderBrandingSummary();
}

function collectBranding() {
  return {
    logo_url: state.brandingLogoUrl || null,
    primary_color: els.brandingPrimaryColor.value.trim() || null,
    phone: els.brandingPhone.value.trim() || null,
    email_contact: els.brandingEmail.value.trim() || null,
    website: els.brandingWebsite.value.trim() || null,
    legal_mention: els.brandingLegalMention.value.trim() || null,
  };
}

async function saveBranding() {
  els.saveBranding.disabled = true;
  try {
    const branding = collectBranding();
    const payload = await api("/organization-branding", {
      method: "PUT",
      body: JSON.stringify(branding),
    });
    applyBranding(payload.branding);
    state.brandingEditorOpen = false;
    setStatus(els.brandingStatus, "✓ Saved");
    window.setTimeout(() => setStatus(els.brandingStatus, ""), 2000);
  } catch (error) {
    setStatus(els.brandingStatus, error.message, true);
  } finally {
    updateUiState();
  }
}

function skipBranding() {
  state.brandingEditorOpen = false;
  setStatus(els.brandingStatus, "");
  updateUiState();
}

function openBrandingEditor() {
  state.brandingEditorOpen = true;
  setStatus(els.brandingStatus, "");
  updateUiState();
}

function renderBrandingSummary() {
  if (!els.brandingSummary) return;
  if (!state.user) {
    els.brandingSummary.innerHTML = "";
    return;
  }
  const branding = state.branding || {};
  const configured = Boolean(
    branding.logo_url
    || branding.primary_color
    || branding.phone
    || branding.email_contact
    || branding.website
    || branding.legal_mention
  );
  const color = branding.primary_color || "#d7dde5";
  els.brandingSummary.innerHTML = `
    <div class="brandingSummaryRow">
      <div class="brandingIdentity">
        <span class="brandingSwatch" style="background:${color}"></span>
        <span>${configured ? "Customization configured" : "Not customized"}</span>
        ${configured ? "<strong>✓</strong>" : ""}
      </div>
      <button type="button" data-open-branding>${configured ? "Edit" : "Configure"}</button>
    </div>
  `;
}

async function handleLogoUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    state.brandingLogoUrl = await logoDataUrl(file);
    renderLogoPreview();
    setStatus(els.brandingStatus, "");
  } catch (error) {
    setStatus(els.brandingStatus, error.message, true);
  }
}

function logoDataUrl(file) {
  if (!["image/png", "image/jpeg", "image/svg+xml"].includes(file.type)) {
    throw new Error("PNG, JPG, or SVG logo only.");
  }
  if (file.type === "image/svg+xml") return readFileAsDataUrl(file);
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const scale = Math.min(1, 300 / image.width);
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(image.width * scale));
      canvas.height = Math.max(1, Math.round(image.height * scale));
      const context = canvas.getContext("2d");
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL(file.type, 0.9));
    };
    image.onerror = () => reject(new Error("Logo cannot be read."));
    readFileAsDataUrl(file).then((dataUrl) => {
      image.src = dataUrl;
    }).catch(reject);
  });
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Unable to read the logo."));
    reader.readAsDataURL(file);
  });
}

function renderLogoPreview() {
  els.brandingLogoPreview.innerHTML = state.brandingLogoUrl
    ? `<img src="${state.brandingLogoUrl}" alt="Logo">`
    : "";
}

async function refreshSession() {
  try {
    const payload = await api("/auth/me");
    state.user = payload.user;
    els.logout.disabled = false;
    setStatus(els.authStatus, `Signed in: ${state.user.email}`);
    await setOrganizationFromUser();
  } catch {
    state.token = "";
    state.user = null;
    els.logout.disabled = true;
    setStatus(els.authStatus, "Not signed in");
  }
  updateUiState();
}

async function loadQuestionnaire() {
  state.profileId = state.organization?.business_profile_id || state.profileId || "roof_insulation_seller";
  els.profileSelect.value = state.profileId;
  state.questionnaire = await api(`/business-profiles/${state.profileId}/questionnaire`);
  if (!state.user) state.organization = null;
  state.project = null;
  state.rooms = [defaultRoom()];
  state.answersSaved = false;
  state.latestAnswers = null;
  state.simulationRuns = [];
  state.latestReportId = null;
  state.thermalLinks = [];
  state.simulationStatus = "idle";
  state.projectDraftOpen = false;
  els.createProject.disabled = true;
  setSaveAnswersDisabled(true);
  els.runSimulation.disabled = true;
  els.addRoomMenuButton.disabled = true;
  els.roomTypeMenu.hidden = true;
  setStatus(els.projectStatus, "");
  setStatus(els.answersStatus, "");
  els.simulationRuns.innerHTML = "";
  els.resultSummary.innerHTML = "";
  renderQuestionnaire();
  renderRooms();
  updateUiState();
}

async function refreshProjects() {
  if (!state.organization) {
    els.projectSelect.innerHTML = "";
    els.projectSelect.hidden = true;
    els.emptyProjects.hidden = false;
    els.loadProject.disabled = true;
    return;
  }
  const payload = await api("/projects");
  const hasProjects = payload.projects.length > 0;
  els.projectSelect.innerHTML = payload.projects
    .map((project) => `<option value="${project.id}">${project.name} · ${project.customer_name || "No client"}</option>`)
    .join("");
  els.projectSelect.hidden = !hasProjects;
  els.emptyProjects.hidden = hasProjects;
  els.emptyProjects.textContent = "No project for this organization. Create one above.";
  els.loadProject.disabled = !hasProjects;
  if (!hasProjects) {
    startNewProject();
  } else {
    state.projectDraftOpen = false;
    setStatus(els.projectStatus, "");
  }
}

function renderQuestionnaire() {
  els.questionnaireIntro.textContent = questionnaireIntroLabel();
  const html = [];
  for (const section of state.questionnaire.sections) {
    const visibleQuestions = section.questions.filter((question) => !hiddenQuestionIds.has(question.id));
    if (!visibleQuestions.length) continue;
    html.push(`<div class="sectionTitle"><h3>${section.label}</h3></div>`);
    for (const question of visibleQuestions) {
      html.push(renderQuestion(question));
    }
  }
  els.questionnaireForm.innerHTML = html.join("");
  applyDefaults();
  syncPositionOptions();
  updateCoolingVisibility();
  updateWeatherVisibility();
}

function questionnaireIntroLabel() {
  if (state.profileId === "roof_insulation_seller") {
    return "Roof insulation questionnaire";
  }
  if (state.profileId === "reflective_roof_seller") {
    return "Reflective roof questionnaire";
  }
  return "Project questionnaire";
}

function renderQuestion(question) {
  const conditionalClass = question.id.startsWith("cooling_setpoint_")
    ? " conditionalCooling"
    : question.id === "annual_weather_year"
      ? " conditionalHistoricalWeather"
      : "";
  if (question.type === "select") {
    const options = (question.options || [])
      .map((option) => `<option value="${option.id}">${option.label}</option>`)
      .join("");
    return `<label class="${conditionalClass.trim()}">${question.label}<select name="${question.id}">${options}</select></label>`;
  }
  if (question.type === "boolean") {
    const selected = question.default ? "true" : "false";
    return `<div class="booleanQuestion${conditionalClass}">
      <span class="fieldLabel">${question.label}</span>
      <div class="booleanPills">
        <label>
          <input id="${question.id}_false" name="${question.id}" type="radio" value="false" ${selected === "false" ? "checked" : ""}>
          <span>No</span>
        </label>
        <label>
          <input id="${question.id}_true" name="${question.id}" type="radio" value="true" ${selected === "true" ? "checked" : ""}>
          <span>Yes</span>
        </label>
      </div>
    </div>`;
  }
  const value = question.default ?? "";
  const inputType = question.type === "number" ? "number" : "text";
  return `<label class="${conditionalClass.trim()}">${question.label}<input name="${question.id}" type="${inputType}" value="${value}"></label>`;
}

function hasGlobalCooling() {
  return getField("has_cooling", "false") === "true";
}

function updateCoolingVisibility() {
  const hasCooling = hasGlobalCooling();
  document.querySelectorAll(".conditionalCooling").forEach((element) => {
    element.hidden = !hasCooling;
  });
  if (!hasCooling) {
    state.rooms = state.rooms.map((room) => ({...room, has_cooling: false}));
  }
  renderRooms();
}

function updateWeatherVisibility() {
  const selector = els.questionnaireForm.elements.namedItem("annual_weather_type");
  const historical = !selector || selector.value === "historical";
  document.querySelectorAll(".conditionalHistoricalWeather").forEach((element) => {
    element.hidden = !historical;
  });
}

const positionOptions = {
  house: [
    ["single_storey_house", "Single-storey house"],
    ["multi_storey_house", "Multi-storey house"],
  ],
  apartment: [
    ["apartment_ground_floor", "Ground-floor apartment"],
    ["apartment_middle_floor", "Middle-floor apartment"],
    ["apartment_top_floor", "Top-floor apartment"],
    ["apartment_ground_top_floor", "Ground-floor apartment directly under the roof"],
  ],
};

function syncPositionOptions() {
  const dwellingTypeField = els.questionnaireForm.elements.namedItem("dwelling_type");
  const positionField = els.questionnaireForm.elements.namedItem("position_id");
  if (!dwellingTypeField || !positionField) return;
  const options = allowedPositionOptions(dwellingTypeField.value);
  const current = positionField.value;
  positionField.innerHTML = options
    .map(([value, label]) => `<option value="${value}">${label}</option>`)
    .join("");
  positionField.value = options.some(([value]) => value === current) ? current : options[0][0];
}

function allowedPositionOptions(dwellingType) {
  if (dwellingType !== "apartment") return positionOptions.house;
  if (["reflective_roof_seller", "roof_insulation_seller"].includes(state.profileId)) {
    return positionOptions.apartment.filter(([value]) => (
      value === "apartment_top_floor" || value === "apartment_ground_top_floor"
    ));
  }
  return positionOptions.apartment;
}

function applyDefaults() {
  setField("project_name", els.projectName.value);
  setField("postal_code", "80202");
  setField("address", "");
  setField("annual_weather_type", "typical");
  setField("annual_weather_year", 2023);
  setField("dwelling_type", "house");
  setField("position_id", "single_storey_house");
  setField("period_id", "2001_2012_good_insulation");
  setField("heating_ref", "electric_radiator");
  setField("heating_setpoint_c", 19);
  setField("heating_energy_price_eur_kwh", 0.25);
}

function markUnsaved() {
  if (!state.project) return;
  state.answersSaved = false;
  state.simulationStatus = state.simulationRuns.length ? "success" : "idle";
  updateUiState();
}

function setField(name, value) {
  const field = els.questionnaireForm.elements.namedItem(name);
  if (!field) return;
  if (field.length && field[0]?.type === "radio") {
    [...field].forEach((option) => {
      option.checked = String(option.value) === String(value);
    });
    return;
  }
  field.value = value;
}

function getField(name, fallback = "") {
  const field = els.questionnaireForm.elements.namedItem(name);
  return field ? field.value : fallback;
}

function defaultRoom() {
  return roomPreset("living");
}

function roomPreset(kind) {
  const presets = {
    living: ["Living room", "living", 24, 4.0, 5.0, 2.5, "exterior"],
    bedroom: ["Bedroom", "bedroom", 12, 1.5, 3.5, 2.5, "exterior"],
    kitchen: ["Kitchen", "kitchen", 10, 1.2, 3.2, 2.5, "exterior"],
    bathroom: ["Bathroom", "bathroom", 6, 0.6, 2.5, 2.5, "exterior"],
    toilet: ["Toilet", "utility", 2, 0.3, 1.4, 2.5, "exterior"],
    office: ["Office", "office", 9, 1.2, 3.0, 2.5, "exterior"],
    corridor: ["Hallway", "corridor", 6, 0.0, 2.5, 2.5, "interior"],
    staircase: ["Staircase", "staircase", 6, 0.0, 2.5, 4.5, "interior"],
    utility: ["Utility room", "utility", 5, 0.4, 2.2, 2.5, "exterior"],
    other: ["Room", "other", 15, 1.2, 4.0, 2.5, "exterior"],
  };
  const [name, type, area, windowArea, wallLength, height, exteriorContact] = presets[kind] || presets.other;
  return {
    name,
    type,
    floor_area_m2: area,
    height_m: height,
    orientation: "S",
    window_area_m2: windowArea,
    wall_length_m: wallLength,
    exterior_contact: exteriorContact,
    mask_factor: 1,
    has_roof: true,
    has_ground_floor: true,
    has_cooling: false,
  };
}

function roomFieldVisible(field, room = null) {
  if (field === "has_cooling") return hasGlobalCooling();
  if (["name", "type", "floor_area_m2", "height_m", "exterior_contact"].includes(field)) return true;
  if (state.profileId === "heat_pump_seller") return false;
  if (room && room.exterior_contact !== "exterior" && ["orientation", "wall_length_m"].includes(field)) {
    return false;
  }
  if (["roof_insulation_seller", "reflective_roof_seller"].includes(state.profileId)) {
    return ["has_roof", "orientation", "wall_length_m"].includes(field);
  }
  return ["orientation", "window_area_m2", "wall_length_m", "mask_factor"].includes(field);
}

function renderRoomField(field, html, room = null) {
  return roomFieldVisible(field, room) ? html : "";
}

function renderRooms() {
  const rooms = roomsWithIds(state.rooms);
  els.rooms.innerHTML = rooms.map((room, index) => `
    <div class="room" data-room-index="${index}" data-room-id="${room.id}">
      <div class="roomTitle">
        <h3>Room ${index + 1}</h3>
        <button class="removeRoom" type="button" data-remove-room="${index}">Remove</button>
      </div>
      ${renderRoomField("name", `<label>Name<input data-room-field="name" value="${escapeHtml(room.name)}"></label>`, room)}
      ${renderRoomField("type", `<label>Type
        <select data-room-field="type">
          ${option("living", "Living room", room.type)}
          ${option("bedroom", "Bedroom", room.type)}
          ${option("kitchen", "Kitchen", room.type)}
          ${option("bathroom", "Bathroom", room.type)}
          ${option("office", "Office", room.type)}
          ${option("corridor", "Hallway / entrance", room.type)}
          ${option("staircase", "Staircase", room.type)}
          ${option("utility", "Toilet / utility room", room.type)}
          ${option("other", "Other", room.type)}
        </select>
      </label>`, room)}
      ${renderRoomField("floor_area_m2", `<label>Area m²<input data-room-field="floor_area_m2" type="number" value="${room.floor_area_m2}"></label>`, room)}
      ${renderRoomField("height_m", `<label>Height m<input data-room-field="height_m" type="number" value="${room.height_m}"></label>`, room)}
      ${renderRoomField("exterior_contact", `<label>Main boundary type
        <select data-room-field="exterior_contact">
          ${option("exterior", "Facade(s) facing outside", room.exterior_contact || "exterior")}
          ${option("interior", "Interior room (no exterior wall)", room.exterior_contact || "exterior")}
          ${option("unheated_space", "Against an unheated space (garage, cellar, attic)", room.exterior_contact || "exterior")}
          ${option("party", "Against a neighbor or party wall", room.exterior_contact || "exterior")}
        </select>
      </label>`, room)}
      ${renderRoomField("orientation", `<label>Orientation
        <select data-room-field="orientation">
          ${["N", "E", "S", "W", "SE", "SW"].map((value) => option(value, value, room.orientation || room.facades?.[0]?.orientation || "S")).join("")}
        </select>
      </label>`, room)}
      ${renderRoomField("window_area_m2", `<label>Glazing m²<input data-room-field="window_area_m2" type="number" value="${room.window_area_m2 ?? room.facades?.[0]?.window_area_m2 ?? 0}"></label>`, room)}
      ${renderRoomField("wall_length_m", `<label>Facade length m<input data-room-field="wall_length_m" type="number" value="${room.wall_length_m ?? room.facades?.[0]?.wall_length_m ?? 4}"></label>`, room)}
      ${renderRoomField("mask_factor", `<label>Solar shading
        <select data-room-field="mask_factor">
          ${option("1", "No shading", String(room.mask_factor ?? room.facades?.[0]?.mask_factor ?? 1))}
          ${option("0.85", "Light shading", String(room.mask_factor ?? room.facades?.[0]?.mask_factor ?? 1))}
          ${option("0.65", "Medium shading", String(room.mask_factor ?? room.facades?.[0]?.mask_factor ?? 1))}
          ${option("0.4", "Strong shading", String(room.mask_factor ?? room.facades?.[0]?.mask_factor ?? 1))}
        </select>
      </label>`, room)}
      ${renderRoomField("has_roof", `<label>Under roof
        <select data-room-field="has_roof">
          ${option("true", "Yes", String(room.has_roof))}
          ${option("false", "No", String(room.has_roof))}
        </select>
      </label>`, room)}
      ${renderRoomField("has_cooling", `<div class="booleanQuestion roomBooleanQuestion">
        <span class="fieldLabel">Cooled room</span>
        <div class="booleanPills">
          <label>
            <input data-room-field="has_cooling" name="room_${index}_has_cooling" type="radio" value="false" ${String(room.has_cooling) !== "true" ? "checked" : ""}>
            <span>No</span>
          </label>
          <label>
            <input data-room-field="has_cooling" name="room_${index}_has_cooling" type="radio" value="true" ${String(room.has_cooling) === "true" ? "checked" : ""}>
            <span>Yes</span>
          </label>
        </div>
      </div>`, room)}
      ${renderConnections(room, rooms)}
    </div>
  `).join("");
}

function option(value, label, selected) {
  return `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function roomsWithIds(rooms) {
  const used = new Set();
  return rooms.map((room, index) => {
    let id = room.id || slugify(room.name || `room-${index + 1}`) || `room_${index + 1}`;
    if (used.has(id)) id = `${id}_${index + 1}`;
    used.add(id);
    return {...room, id};
  });
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function pairKey(roomA, roomB) {
  return [roomA, roomB].sort().join("__");
}

function linkForPair(roomA, roomB) {
  return state.thermalLinks.find((link) => pairKey(link.room_a, link.room_b) === pairKey(roomA, roomB));
}

function roomLabel(room, index) {
  return room.name || `Room ${index + 1}`;
}

function renderConnections(room, rooms) {
  if (rooms.length < 2) return "";
  const connectedIds = rooms
    .filter((other) => other.id !== room.id && linkForPair(room.id, other.id))
    .map((other) => other.id);
  const ownedLinks = state.thermalLinks
    .filter((link) => link.room_a === room.id || link.room_b === room.id)
    .filter((link) => rooms.some((candidate) => candidate.id === otherRoomId(link, room.id)))
    .filter((link) => connectionOwnerRoomId(link, rooms) === room.id);
  return `
    <div class="connectionFields">
      <div class="connectionPills" role="group" aria-label="Connections with other rooms">
        <span>Connections with other rooms</span>
        <div>
          ${rooms
            .filter((other) => other.id !== room.id)
            .map((other, index) => renderConnectionPill(room, other, index, connectedIds.includes(other.id)))
            .join("")}
        </div>
      </div>
      ${ownedLinks.map((link) => renderConnectionParams(link, rooms, room.id)).join("")}
    </div>
  `;
}

function renderConnectionPill(room, other, index, isConnected) {
  return `
    <button
      type="button"
      class="connectionPill ${isConnected ? "selected" : ""}"
      data-toggle-connection="true"
      data-room-id="${room.id}"
      data-other-room-id="${other.id}"
      aria-pressed="${isConnected ? "true" : "false"}"
    >
      ${isConnected ? "✓ " : ""}${roomLabel(other, index)}
    </button>
  `;
}

function connectionOwnerRoomId(link, rooms) {
  if (link.owner_room_id && rooms.some((room) => room.id === link.owner_room_id)) {
    return link.owner_room_id;
  }
  const roomAIndex = rooms.findIndex((room) => room.id === link.room_a);
  const roomBIndex = rooms.findIndex((room) => room.id === link.room_b);
  return roomAIndex <= roomBIndex ? link.room_a : link.room_b;
}

function otherRoomId(link, roomId) {
  return link.room_a === roomId ? link.room_b : link.room_a;
}

function renderConnectionParams(link, rooms, roomId) {
  const otherId = otherRoomId(link, roomId);
  const otherIndex = rooms.findIndex((room) => room.id === otherId);
  const other = rooms[otherIndex];
  const key = pairKey(link.room_a, link.room_b);
  return `
    <div class="connectionParams" data-link-key="${key}">
      <h4>Connection to ${roomLabel(other || {name: otherId}, otherIndex)}</h4>
      <label>Shared area m²<input data-link-field="area_m2" type="number" min="0.1" step="0.1" value="${link.area_m2 ?? 4}"></label>
    </div>
  `;
}

function syncRoomsFromDom(connectionChange = null) {
  const existingLinks = new Map(state.thermalLinks.map((link) => [pairKey(link.room_a, link.room_b), link]));
  document.querySelectorAll("[data-link-key]").forEach((linkElement) => {
    const key = linkElement.dataset.linkKey;
    const existing = existingLinks.get(key);
    if (!existing) return;
    existing.area_m2 = Number(linkElement.querySelector('[data-link-field="area_m2"]').value || existing.area_m2);
  });
  const roomElements = [...document.querySelectorAll(".room")];
  const rooms = roomElements.map((roomElement, index) => {
    const value = (field, fallback) => {
      const checkedFieldElement = roomElement.querySelector(`[data-room-field="${field}"]:checked`);
      if (checkedFieldElement) return checkedFieldElement.value;
      const fieldElement = roomElement.querySelector(`[data-room-field="${field}"]`);
      return fieldElement ? fieldElement.value : fallback;
    };
    const exteriorContact = value("exterior_contact", "exterior");
    const orientation = value("orientation", "S");
    const windowArea = Number(value("window_area_m2", 0));
    const wallLength = Number(value("wall_length_m", 4));
    const maskFactor = Number(value("mask_factor", 1));
    return {
      id: roomElement.dataset.roomId || `room_${index + 1}`,
      name: value("name", "Room"),
      type: value("type", "living"),
      floor_area_m2: Number(value("floor_area_m2", 20)),
      height_m: Number(value("height_m", 2.5)),
      has_cooling: hasGlobalCooling() && value("has_cooling", "false") === "true",
      has_roof: value("has_roof", "true") === "true",
      has_ground_floor: true,
      orientation,
      window_area_m2: windowArea,
      wall_length_m: wallLength,
      mask_factor: maskFactor,
      exterior_contact: exteriorContact,
      facades: exteriorContact === "exterior" ? [{
        orientation,
        window_area_m2: windowArea,
        wall_length_m: wallLength,
        mask_factor: maskFactor,
      }] : [],
    };
  });
  state.rooms = roomsWithIds(rooms);
  const roomIds = new Set(state.rooms.map((room) => room.id));
  if (!connectionChange) {
    state.thermalLinks = [...existingLinks.values()]
      .filter((link) => roomIds.has(link.room_a) && roomIds.has(link.room_b));
    return;
  }
  const activeLinks = new Map();
  roomElements.forEach((roomElement) => {
    const roomId = roomElement.dataset.roomId;
    if (connectionChange && roomId !== connectionChange.roomId) {
      return;
    }
    const selectedIds = connectionChange && roomId === connectionChange.roomId
      ? connectionChange.selectedIds
      : [];
    selectedIds.forEach((otherId) => {
      if (!otherId || otherId === roomId) return;
      const key = pairKey(roomId, otherId);
      const existing = existingLinks.get(key) || {};
      const [roomA, roomB] = [roomId, otherId].sort();
      activeLinks.set(key, {
        room_a: roomA,
        room_b: roomB,
        area_m2: Number(existing.area_m2 ?? 4),
        owner_room_id: connectionChange?.roomId || existing.owner_room_id || roomA,
      });
    });
  });
  if (connectionChange) {
    state.thermalLinks = state.thermalLinks
      .filter((link) => link.room_a !== connectionChange.roomId && link.room_b !== connectionChange.roomId)
      .concat([...activeLinks.values()]);
  } else {
    state.thermalLinks = [...activeLinks.values()];
  }
}

function collectAnswers() {
  syncRoomsFromDom();
  const formData = new FormData(els.questionnaireForm);
  const answers = Object.fromEntries(formData.entries());
  answers.project_name = els.projectName.value;
  answers.rooms = state.rooms;
  answers.thermal_layout = {
    type: state.rooms.length < 2 ? "single_room" : "manual",
    connections: state.thermalLinks.map((link) => ({
      room_a: link.room_a,
      room_b: link.room_b,
      area_m2: link.area_m2,
    })),
  };
  for (const key of ["heating_setpoint_c", "cooling_setpoint_c", "cooling_setpoint_day_c", "cooling_setpoint_night_c", "annual_weather_year"]) {
    if (answers[key] !== undefined && answers[key] !== "") answers[key] = Number(answers[key]);
  }
  if (answers.heating_energy_price_eur_kwh !== undefined && answers.heating_energy_price_eur_kwh !== "") {
    answers.heating_energy_price_eur_kwh = Number(answers.heating_energy_price_eur_kwh);
  }
  return answers;
}

function selectedProfile() {
  return state.profiles.find((profile) => profile.id === state.profileId) || {label: state.profileId};
}

async function login() {
  state.authSubmitting = "login";
  updateUiState();
  try {
    const payload = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: els.email.value,
        password: els.password.value,
      }),
    });
    setSession(payload);
    state.profileId = state.organization.business_profile_id;
    els.profileSelect.value = state.profileId;
    await setOrganizationFromUser(payload.organization);
  } catch (error) {
    setStatus(els.authStatus, error.message, true);
  } finally {
    state.authSubmitting = "";
    updateUiState();
  }
}

async function logout() {
  try {
    await api("/auth/logout", {method: "POST"});
  } catch {
  }
  state.token = "";
  state.user = null;
  state.organization = null;
  state.project = null;
  state.selectedOrganization = null;
  state.authSubmitting = "";
  state.answersSaved = false;
  state.latestAnswers = null;
  state.simulationRuns = [];
  state.latestReportId = null;
  state.simulationStatus = "idle";
  state.branding = null;
  state.brandingLogoUrl = "";
  state.brandingEditorOpen = false;
  els.logout.disabled = true;
  els.createProject.disabled = true;
  setSaveAnswersDisabled(true);
  els.runSimulation.disabled = true;
  els.projectSelect.innerHTML = "";
  els.simulationRuns.innerHTML = "";
  els.resultSummary.innerHTML = "";
  setStatus(els.authStatus, "Signed out");
  setStatus(els.brandingStatus, "");
  applyBranding({});
  updateUiState();
}

function setSession(payload) {
  state.token = payload.access_token;
  state.user = payload.user;
  state.organization = payload.organization;
  state.selectedOrganization = {
    ...payload.organization,
    exists: true,
  };
  els.logout.disabled = false;
  setStatus(els.authStatus, `Signed in: ${state.user.email}`);
  updateUiState();
}

async function setOrganizationFromUser(organization = null) {
  if (organization) {
    state.organization = organization;
  } else {
    const payload = await api("/organizations");
    state.organization = payload.organizations[0] || null;
  }
  if (!state.organization) {
    setStatus(els.authStatus, "No organization is associated with this account.", true);
    updateUiState();
    return;
  }
  state.profileId = state.organization.business_profile_id;
  els.profileSelect.value = state.profileId;
  state.questionnaire = await api(`/business-profiles/${state.profileId}/questionnaire`);
  renderQuestionnaire();
  if (state.pendingDemoAnswers) {
    applyAnswers(state.pendingDemoAnswers);
    state.projectDraftOpen = true;
  }
  renderRooms();
  els.createProject.disabled = false;
  await refreshProjects();
  await loadBranding();
  setStatus(els.authStatus, `Signed in: ${state.user.email}`);
  updateUiState();
}

async function createProject() {
  els.createProject.disabled = true;
  try {
    state.project = await api("/projects", {
      method: "POST",
      body: JSON.stringify({
        organization_id: state.organization.id,
        name: els.projectName.value,
        customer_name: els.customerName.value,
      }),
    });
    state.answersSaved = false;
    state.latestAnswers = null;
    state.simulationRuns = [];
    state.latestReportId = null;
    state.thermalLinks = [];
    state.simulationStatus = "idle";
    state.projectDraftOpen = false;
    setSaveAnswersDisabled(false);
    els.runSimulation.disabled = true;
    await refreshProjects();
    setStatus(els.projectStatus, `✓ Project created: ${state.project.name} — ${state.project.customer_name || "No client"}`);
    if (state.pendingDemoAnswers) {
      applyAnswers(state.pendingDemoAnswers);
    }
    updateUiState();
  } catch (error) {
    setStatus(els.projectStatus, error.message, true);
  } finally {
    updateUiState();
  }
}

function startNewProject() {
  state.project = null;
  state.answersSaved = false;
  state.latestAnswers = null;
  state.simulationRuns = [];
  state.latestReportId = null;
  state.thermalLinks = [];
  state.simulationStatus = "idle";
  state.projectDraftOpen = true;
  state.rooms = [defaultRoom()];
  els.projectName.value = "Client house";
  els.customerName.value = "Test client";
  els.resultSummary.innerHTML = "";
  els.simulationRuns.innerHTML = "";
  setStatus(els.projectStatus, "New project ready to create.");
  setStatus(els.answersStatus, "");
  renderRooms();
  updateUiState();
}

async function loadProject() {
  const projectId = els.projectSelect.value;
  if (!projectId) return;
  const payload = await api(`/projects/${projectId}`);
  state.project = payload.project;
  state.projectDraftOpen = false;
  els.projectName.value = state.project.name;
  els.customerName.value = state.project.customer_name || "";
  setSaveAnswersDisabled(false);
  state.latestAnswers = payload.latest_answers || null;
  state.answersSaved = Boolean(state.latestAnswers);
  state.simulationRuns = payload.simulation_runs;
  state.latestReportId = latestUsefulReportId();
  state.simulationStatus = usefulReportRuns().length ? "success" : "idle";
  els.runSimulation.disabled = !state.answersSaved;
  if (state.latestAnswers) {
    applyAnswers(state.latestAnswers.answers);
    const reportCount = usefulReportRuns().length;
    setStatus(
      els.answersStatus,
      reportCount
        ? `Latest answers: version ${state.latestAnswers.version}. Simulation already run, reports available.`
        : `Latest answers: version ${state.latestAnswers.version}`,
    );
  }
  renderSimulationRuns();
  await renderLatestSummary();
  setStatus(els.projectStatus, `Project loaded: ${state.project.id}`);
  updateUiState();
}

function applyAnswers(answers) {
  els.projectName.value = answers.project_name || state.project?.name || els.projectName.value;
  for (const [key, value] of Object.entries(answers)) {
    if (key === "rooms" || key === "thermal_layout") continue;
    setField(key, value);
  }
  syncPositionOptions();
  updateCoolingVisibility();
  if (answers.rooms) {
    state.rooms = answers.rooms.map(roomFromAnswer);
    state.thermalLinks = (answers.thermal_layout?.connections || []).map((connection) => ({
      room_a: connection.room_a,
      room_b: connection.room_b,
      area_m2: Number(connection.area_m2 ?? 4),
    }));
    renderRooms();
  }
  updateUiState();
}

function roomFromAnswer(room) {
  return {
    id: room.id,
    name: room.name,
    type: room.type,
    floor_area_m2: room.floor_area_m2,
    height_m: room.height_m,
    orientation: room.facades?.[0]?.orientation || "S",
    window_area_m2: room.facades?.[0]?.window_area_m2 || 0,
    wall_length_m: room.facades?.[0]?.wall_length_m || 4,
    exterior_contact: room.exterior_contact || "exterior",
    mask_factor: room.facades?.[0]?.mask_factor ?? 1,
    has_roof: Boolean(room.has_roof),
    has_ground_floor: room.has_ground_floor !== false,
    has_cooling: room.has_cooling === true,
  };
}

async function saveAnswers() {
  setSaveAnswersDisabled(true);
  try {
    const answers = collectAnswers();
    if (state.latestAnswers && sameAnswers(answers, state.latestAnswers.answers)) {
      state.answersSaved = true;
      state.simulationStatus = usefulReportRuns().length ? "success" : "idle";
      setStatus(
        els.answersStatus,
        usefulReportRuns().length
          ? `Answers unchanged: simulation already run, reports available.`
          : `Answers unchanged: version ${state.latestAnswers.version}`,
      );
      updateUiState();
      return;
    }
    const saved = await api(`/projects/${state.project.id}/answers`, {
      method: "POST",
      body: JSON.stringify({answers}),
    });
    state.latestAnswers = saved;
    state.answersSaved = true;
    state.simulationStatus = usefulReportRuns().length ? "success" : "idle";
    state.lastSimulationError = "";
    setStatus(els.answersStatus, `Answers saved: version ${saved.version}`);
    updateUiState();
  } catch (error) {
    state.lastSimulationError = error.message;
    setStatus(els.answersStatus, error.message, true);
  } finally {
    updateUiState();
  }
}

async function runSimulation() {
  try {
    state.simulationStatus = "loading";
    updateUiState();
    const batch = await api(`/projects/${state.project.id}/simulations`, {method: "POST"});
    state.simulationRuns = batch.simulation_runs;
    state.latestReportId = latestUsefulReportId();
    state.simulationStatus = "success";
    renderSimulationRuns();
    await renderLatestSummary();
    setStatus(els.answersStatus, "Simulation complete");
  } catch (error) {
    state.simulationStatus = "error";
    state.lastSimulationError = error.message;
    setStatus(els.answersStatus, error.message, true);
  } finally {
    updateUiState();
  }
}

function renderSimulationRuns(runs = state.simulationRuns) {
  state.simulationRuns = runs;
  const visibleRuns = usefulReportRuns();
  if (!runs.length) {
    els.simulationRuns.innerHTML = "";
    return;
  }
  if (!visibleRuns.length) {
    els.simulationRuns.innerHTML = `
      <div class="stateBox">Simulations exist for older answers. Save and run again to generate reports for the displayed data.</div>
    `;
    return;
  }
  const hiddenCount = runs.length - visibleRuns.length;
  els.simulationRuns.innerHTML = `
    ${hiddenCount > 0 ? `<div class="stateBox success">Showing ${visibleRuns.length} useful report${visibleRuns.length > 1 ? "s" : ""}. ${hiddenCount} technical simulation${hiddenCount > 1 ? "s" : ""} hidden.</div>` : ""}
    ${visibleRuns.map((run) => `
    <div class="run">
      <div>
        <strong>${simulationRunLabel(run)}</strong>
        <p>${simulationRunStatus(run)}</p>
      </div>
      <div class="runActions">
        <button type="button" data-open-report="${run.id}">HTML report</button>
        <button type="button" data-download-report="${run.id}">PDF</button>
      </div>
    </div>
  `).join("")}
  `;
}

function simulationRunLabel(run) {
  if (run.adaptation_id === "roof_insulation" && run.season === "annual") {
    return "Real-weather annual simulation";
  }
  if (run.adaptation_id === "roof_insulation" && run.season === "winter" && run.role === "primary") {
    return "Winter simulation";
  }
  if (run.adaptation_id === "roof_insulation" && run.season === "summer") {
    return "Summer impact";
  }
  if (run.adaptation_id === "reflective_roof" && run.season === "summer" && run.role === "primary") {
    return "June to September simulation";
  }
  if (run.adaptation_id === "reflective_roof" && run.season === "summer" && run.role === "secondary") {
    return "5-day heatwave simulation";
  }
  const adaptationLabels = {
    reflective_roof: "Reflective coating",
    roof_insulation: "Roof insulation",
    better_windows: "Windows",
    solar_protection: "Solar protection",
    heat_pump: "Heat pump",
  };
  const seasonLabels = {
    summer: "Summer comfort",
    winter: "Winter heating",
    annual: "Full year",
  };
  const roleLabels = {
    primary: "main report",
    secondary: "supplementary report",
    annual: "annual report",
  };
  return [
    adaptationLabels[run.adaptation_id] || run.adaptation_id,
    seasonLabels[run.season] || run.season,
    roleLabels[run.role] || run.role,
  ].join(" · ");
}

function simulationRunStatus(run) {
  const statusLabel = run.status === "completed" ? "Simulation complete" : run.status;
  if (["reflective_roof", "roof_insulation"].includes(run.adaptation_id)) {
    return statusLabel;
  }
  return `${statusLabel} · ${run.id}`;
}

async function openReport(simulationRunId) {
  const reportWindow = window.open("", "_blank");
  if (!reportWindow) {
    throw new Error("The browser blocked the report window.");
  }
  reportWindow.document.write("<p>Loading report...</p>");
  const headers = state.token ? {Authorization: `Bearer ${state.token}`} : {};
  const response = await fetch(`/simulation-runs/${simulationRunId}/report-html`, {
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    reportWindow.close();
    throw new Error("Report unavailable.");
  }
  const html = await response.text();
  reportWindow.document.open();
  reportWindow.document.write(html);
  reportWindow.document.close();
}

async function downloadReportPdf(simulationRunId) {
  const headers = state.token ? {Authorization: `Bearer ${state.token}`} : {};
  const response = await fetch(`/simulation-runs/${simulationRunId}/report-pdf`, {
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error("PDF unavailable.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = reportPdfFilename(response) || `report-${simulationRunId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function reportPdfFilename(response) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch) return decodeURIComponent(encodedMatch[1]);
  const quotedMatch = disposition.match(/filename="([^"]+)"/i);
  if (quotedMatch) return quotedMatch[1];
  const plainMatch = disposition.match(/filename=([^;]+)/i);
  return plainMatch ? plainMatch[1].trim() : "";
}

async function renderLatestSummary() {
  const runs = usefulReportRuns();
  if (!runs.length) {
    els.resultSummary.innerHTML = "";
    return;
  }
  const latestRun = runs[runs.length - 1];
  const summaryRun = summaryMetricsRun(runs);
  state.latestReportId = latestRun.id;
  const payload = await api(`/simulation-runs/${summaryRun.id}`);
  const summary = payload.result.comparison.summary;
  const headline = summary.headline_metrics;
  const energy = summary.energy_savings;
  const beforeTotals = payload.result.comparison.before.totals;
  const afterTotals = payload.result.comparison.after.totals;
  if (summaryRun.adaptation_id === "reflective_roof") {
    els.resultSummary.innerHTML = `
      <div class="metric accent"><span>Max temperature reduction</span><strong>${formatNumber(headline.max_temperature_reduction_c)} °C</strong></div>
      <div class="metric accent"><span>Hot discomfort avoided</span><strong>${formatInteger(headline.hot_degree_hours_reduced)} °C·h</strong></div>
    `;
    return;
  }
  if (summaryRun.adaptation_id === "roof_insulation") {
    const weatherYear = payload.result.comparison.experiment.weather_year || "real weather";
    els.resultSummary.innerHTML = `
      <div class="metric accent"><span>Estimated savings over a real-weather year</span><strong>${formatNumber(energy.cost_saved_eur)} €</strong></div>
      <div class="metric accent"><span>Heating demand reduced</span><strong>${formatNumber(beforeTotals.heating_thermal_kwh - afterTotals.heating_thermal_kwh)} kWh_th</strong></div>
      <div class="metric"><span>Period</span><strong>Real-weather year ${weatherYear}</strong></div>
    `;
    return;
  }
  els.resultSummary.innerHTML = `
    <div class="metric"><span>Electricity saved</span><strong>${formatNumber(energy.electricity_saved_kwh)} kWh</strong></div>
    <div class="metric"><span>Estimated savings</span><strong>${formatNumber(energy.cost_saved_eur)} €</strong></div>
    <div class="metric"><span>CO₂ avoided</span><strong>${formatNumber(energy.co2_saved_kg)} kg</strong></div>
    <div class="metric"><span>Max temperature reduction</span><strong>${formatNumber(headline.max_temperature_reduction_c)} °C</strong></div>
    <div class="metric"><span>Hot discomfort avoided</span><strong>${formatNumber(headline.hot_degree_hours_reduced)} °C·h</strong></div>
    <div class="metric"><span>Cold discomfort avoided</span><strong>${formatNumber(headline.cold_degree_hours_reduced)} °C·h</strong></div>
  `;
}

function summaryMetricsRun(runs) {
  const reflectivePrimary = runs.find((run) => (
    run.adaptation_id === "reflective_roof" && run.season === "summer" && run.role === "primary"
  ));
  const roofAnnual = runs.find((run) => (
    run.adaptation_id === "roof_insulation" && run.season === "annual"
  ));
  return reflectivePrimary || roofAnnual || runs[runs.length - 1];
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("fr-FR", {maximumFractionDigits: 2});
}

function formatInteger(value) {
  return Number(value || 0).toLocaleString("fr-FR", {maximumFractionDigits: 0});
}

function usefulReportRuns(runs = state.simulationRuns) {
  const answersId = state.latestAnswers?.id || runs[runs.length - 1]?.answers_id;
  const scopedRuns = answersId ? runs.filter((run) => run.answers_id === answersId) : runs;
  const reportRuns = scopedRuns.some((run) => run.adaptation_id === "roof_insulation")
    ? scopedRuns.filter((run) => run.adaptation_id !== "roof_insulation" || run.season === "annual")
    : scopedRuns;
  const latestByScenario = new Map();
  for (const run of reportRuns) {
    latestByScenario.set(`${run.season}:${run.role}`, run);
  }
  return [...latestByScenario.values()];
}

function latestUsefulReportId() {
  const reports = usefulReportRuns();
  return reports.length ? reports[reports.length - 1].id : null;
}

function hasCurrentReports() {
  return Boolean(
    state.latestAnswers
    && state.answersSaved
    && sameAnswers(collectAnswers(), state.latestAnswers.answers)
    && usefulReportRuns().length,
  );
}

function sameAnswers(left, right) {
  return stableStringify(left) === stableStringify(right);
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function renderProgress() {
  const completed = {
    account: Boolean(state.user),
    project: Boolean(state.project),
    dwelling: Boolean(state.answersSaved),
    simulation: usefulReportRuns().length > 0,
  };
  const order = ["account", "project", "dwelling", "simulation"];
  const active = order.find((key) => !completed[key]) || "simulation";
  for (const step of els.progressSteps.querySelectorAll(".step")) {
    const key = step.dataset.step;
    step.classList.toggle("completed", completed[key]);
    step.classList.toggle("active", key === active);
    step.querySelector("span").textContent = completed[key] ? "✓" : String(order.indexOf(key) + 1);
  }
}

function renderProjectSummary() {
  if (!state.project) {
    els.projectSummary.hidden = true;
    els.projectSummary.innerHTML = "";
    return;
  }
  const reports = usefulReportRuns();
  const latest = reports.length
    ? `Latest useful simulation: ${formatDate(reports[reports.length - 1].created_at)} ✓`
    : state.simulationRuns.length
      ? "Latest simulation: older answer version"
      : "Latest simulation: none";
  const postalCode = getField("postal_code", "80202");
  els.projectSummary.hidden = false;
  els.projectSummary.innerHTML = `
    <div class="projectSummaryTitle">📁 ${state.project.name} — ${state.project.customer_name || "No client"}</div>
    <div class="projectSummaryMeta">${state.rooms.length} room${state.rooms.length > 1 ? "s" : ""} | ZIP ${postalCode}</div>
    <div class="projectSummaryMeta">${latest}</div>
    <div class="projectSummaryReports">
      ${reports.length ? reports.map((run) => `
        <div class="reportAction">
          <span>${simulationRunLabel(run)}</span>
          <button type="button" data-open-report="${run.id}">HTML</button>
          <button type="button" data-download-report="${run.id}">PDF</button>
        </div>
      `).join("") : `
        <div class="projectSummaryActions">
          <button type="button" disabled>View HTML report</button>
          <button type="button" disabled>Download PDF</button>
        </div>
      `}
    </div>
  `;
}

function renderSimulationState() {
  els.runSimulation.textContent = state.simulationStatus === "loading"
    ? "Simulation running..."
    : hasCurrentReports()
      ? "Run simulation again"
    : "Run simulation";
  if (state.simulationStatus === "loading") {
    els.simulationState.className = "stateBox";
    els.simulationState.textContent = "Simulation running...";
  } else if (state.simulationStatus === "success" && state.simulationRuns.length) {
    const reports = usefulReportRuns();
    const latestRun = reports[reports.length - 1] || state.simulationRuns[state.simulationRuns.length - 1];
    els.simulationState.className = "stateBox success";
    els.simulationState.textContent = hasCurrentReports()
      ? `✓ Reports available for these answers. You can run again if needed.`
      : `✓ Simulation completed on ${formatDate(latestRun.created_at)}. See the summary.`;
  } else if (state.simulationStatus === "error") {
    els.simulationState.className = "stateBox error";
    els.simulationState.innerHTML = `${state.lastSimulationError || "Simulation error."} <strong>Correct the information, then click Try again.</strong>`;
    els.runSimulation.textContent = "Try again";
  } else {
    els.simulationState.className = "stateBox";
    els.simulationState.textContent = "No simulation run yet. Fill in the questionnaire, then click Run simulation.";
  }
}

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString("fr-FR");
}

function applyDemo(demoId) {
  if (!demoId) return;
  const suffix = Date.now().toString().slice(-6);
  const profileId = demoId;
  els.profileSelect.value = profileId;
  state.profileId = profileId;
  state.selectedOrganization = null;
  els.email.value = `demo.${profileId}.${suffix}@thermaltwin.local`;
  els.password.value = "password123";
  els.projectName.value = demoProjectName(demoId);
  els.customerName.value = "Demo client";
  loadQuestionnaire().then(() => {
    const answers = demoAnswers(demoId);
    state.pendingDemoAnswers = answers;
    for (const [key, value] of Object.entries(answers)) {
      if (key !== "rooms" && key !== "thermal_layout") setField(key, value);
    }
    state.rooms = answers.rooms.map(roomFromAnswer);
    state.thermalLinks = (answers.thermal_layout?.connections || []).map((connection) => ({
      room_a: connection.room_a,
      room_b: connection.room_b,
      area_m2: Number(connection.area_m2 ?? 4),
    }));
    renderRooms();
    state.answersSaved = false;
    setStatus(els.authStatus, "Demo prefilled.");
    updateUiState();
  });
}

function demoProjectName(demoId) {
  if (demoId === "heat_pump_seller") return "Heat pump demo house";
  if (demoId === "solar_protection_seller") return "Solar protection demo house";
  if (demoId === "window_seller") return "Window demo house";
  if (demoId === "roof_insulation_seller") return "Roof insulation demo house";
  return "Reflective roof coating demo house";
}

function demoAnswers(demoId) {
  const common = {
    postal_code: "80202",
    address: "",
    annual_weather_type: "historical",
    annual_weather_year: 2023,
    dwelling_type: "house",
    position_id: "single_storey_house",
    period_id: "2001_2012_good_insulation",
    rooms: [
      {
        name: "Living room",
        type: "living",
        floor_area_m2: 24,
        height_m: 2.5,
        has_roof: true,
        facades: [{orientation: "S", window_area_m2: 4, wall_length_m: 5}],
      },
    ],
  };
  if (demoId === "heat_pump_seller") {
    return {
      ...common,
      current_energy_id: "electricity",
      heating_ref: "electric_radiator",
      heat_emitters_id: "electric_radiators",
      heating_setpoint_c: 19,
    };
  }
  if (demoId === "solar_protection_seller") {
    return {
      ...common,
      window_ref: "double_glazing_standard",
      shutter_ref: "none",
      cooling_setpoint_c: 26,
    };
  }
  if (demoId === "window_seller") {
    return {
      ...common,
      window_ref: "double_glazing_old",
      window_air_leakage_id: "standard",
    };
  }
  if (demoId === "roof_insulation_seller") {
    return {
      ...common,
      roof_insulation_id: "poor",
      roof_color_id: "medium",
      attic_ventilation_id: "attic",
      wall_insulation_id: "standard",
      heating_ref: "electric_radiator",
      heating_setpoint_c: 19,
      heating_energy_price_eur_kwh: 0.25,
    };
  }
  return {
    ...common,
    adaptation_id: "reflective_roof",
    roof_insulation_id: "standard",
    roof_color_id: "dark",
    attic_ventilation_id: "attic",
  };
}

els.login.addEventListener("click", login);
els.logout.addEventListener("click", logout);
els.saveBranding.addEventListener("click", saveBranding);
els.skipBranding.addEventListener("click", skipBranding);
els.brandingSummary.addEventListener("click", (event) => {
  if (event.target.dataset.openBranding !== undefined) openBrandingEditor();
});
els.brandingLogo.addEventListener("change", handleLogoUpload);
els.brandingColorPicker.addEventListener("input", () => {
  els.brandingPrimaryColor.value = els.brandingColorPicker.value;
});
els.brandingPrimaryColor.addEventListener("input", () => {
  if (/^#[0-9a-fA-F]{6}$/.test(els.brandingPrimaryColor.value)) {
    els.brandingColorPicker.value = els.brandingPrimaryColor.value;
  }
});
els.profileSelect.addEventListener("change", () => {
  state.profileId = els.profileSelect.value;
  loadQuestionnaire().catch((error) => setStatus(els.authStatus, error.message, true));
});
els.createProject.addEventListener("click", createProject);
els.newProject.addEventListener("click", startNewProject);
els.loadProject.addEventListener("click", () => loadProject().catch((error) => setStatus(els.projectStatus, error.message, true)));
els.saveAnswers.addEventListener("click", saveAnswers);
els.saveAnswersBottom.addEventListener("click", saveAnswers);
els.runSimulation.addEventListener("click", runSimulation);
els.questionnaireForm.addEventListener("input", markUnsaved);
els.questionnaireForm.addEventListener("change", (event) => {
  if (event.target.name === "dwelling_type") syncPositionOptions();
  if (event.target.name === "has_cooling") updateCoolingVisibility();
  if (event.target.name === "annual_weather_type") updateWeatherVisibility();
  if (event.target.name === "heating_ref") {
    const defaultPrice = defaultHeatingEnergyPrices[event.target.value];
    if (defaultPrice !== undefined) setField("heating_energy_price_eur_kwh", defaultPrice);
  }
  markUnsaved();
});
els.rooms.addEventListener("input", markUnsaved);
els.rooms.addEventListener("change", (event) => {
  if (event.target.dataset.roomField === "exterior_contact") {
    syncRoomsFromDom();
    renderRooms();
  }
  markUnsaved();
});
els.rooms.addEventListener("click", (event) => {
  const toggle = event.target.closest("[data-toggle-connection]");
  if (!toggle) return;
  const roomId = toggle.dataset.roomId;
  const otherRoomId = toggle.dataset.otherRoomId;
  const roomElement = toggle.closest(".room");
  const selectedIds = [...roomElement.querySelectorAll("[data-toggle-connection][aria-pressed='true']")]
    .map((button) => button.dataset.otherRoomId)
    .filter((id) => id !== otherRoomId);
  if (toggle.getAttribute("aria-pressed") !== "true") {
    selectedIds.push(otherRoomId);
  }
  syncRoomsFromDom({roomId, selectedIds});
  markUnsaved();
  renderRooms();
});
els.projectName.addEventListener("input", markUnsaved);
els.addRoomMenuButton.addEventListener("click", () => {
  els.roomTypeMenu.hidden = !els.roomTypeMenu.hidden;
});
els.roomTypeMenu.addEventListener("click", (event) => {
  const roomTypeButton = event.target.closest("[data-room-type]");
  if (!roomTypeButton || !els.roomTypeMenu.contains(roomTypeButton)) return;
  const roomType = roomTypeButton.dataset.roomType;
  if (!roomType) return;
  try {
    syncRoomsFromDom();
  } catch (error) {
    console.error("Unable to sync rooms before adding one.", error);
  }
  state.rooms.push(roomPreset(roomType));
  markUnsaved();
  renderRooms();
  els.roomTypeMenu.hidden = true;
});
els.rooms.addEventListener("click", (event) => {
  const index = event.target.dataset.removeRoom;
  if (index === undefined) return;
  syncRoomsFromDom();
  state.rooms.splice(Number(index), 1);
  if (!state.rooms.length) state.rooms.push(defaultRoom());
  markUnsaved();
  renderRooms();
});
els.simulationRuns.addEventListener("click", (event) => {
  const openReportId = event.target.dataset.openReport;
  const downloadReportId = event.target.dataset.downloadReport;
  if (openReportId) {
    openReport(openReportId).catch((error) => setStatus(els.answersStatus, error.message, true));
  }
  if (downloadReportId) {
    downloadReportPdf(downloadReportId).catch((error) => setStatus(els.answersStatus, error.message, true));
  }
});
els.projectSummary.addEventListener("click", (event) => {
  const openReportId = event.target.dataset.openReport;
  const downloadReportId = event.target.dataset.downloadReport;
  if (openReportId) {
    openReport(openReportId).catch((error) => setStatus(els.answersStatus, error.message, true));
  }
  if (downloadReportId) {
    downloadReportPdf(downloadReportId).catch((error) => setStatus(els.answersStatus, error.message, true));
  }
});

loadProfiles().catch((error) => setStatus(els.authStatus, error.message, true));
