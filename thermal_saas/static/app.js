const state = {
  profiles: [],
  profileId: "",
  questionnaire: null,
  organization: null,
  project: null,
  rooms: [],
  token: localStorage.getItem("thermal_saas_token") || "",
  user: null,
  authStep: "organization",
  selectedOrganization: null,
  answersSaved: false,
  simulationRuns: [],
  latestReportId: null,
  simulationStatus: "idle",
  pendingDemoAnswers: null,
  lastSimulationError: "",
  projectDraftOpen: false,
  authSubmitting: "",
};

const els = {
  email: document.querySelector("#email"),
  password: document.querySelector("#password"),
  register: document.querySelector("#register"),
  login: document.querySelector("#login"),
  logout: document.querySelector("#logout"),
  authStatus: document.querySelector("#authStatus"),
  loggedOutAccount: document.querySelector("#loggedOutAccount"),
  loggedInAccount: document.querySelector("#loggedInAccount"),
  connectedEmail: document.querySelector("#connectedEmail"),
  connectedOrganization: document.querySelector("#connectedOrganization"),
  connectedProfile: document.querySelector("#connectedProfile"),
  organizationStep: document.querySelector("#organizationStep"),
  credentialsStep: document.querySelector("#credentialsStep"),
  continueToCredentials: document.querySelector("#continueToCredentials"),
  backToOrganization: document.querySelector("#backToOrganization"),
  selectedOrganizationSummary: document.querySelector("#selectedOrganizationSummary"),
  organizationLookupStatus: document.querySelector("#organizationLookupStatus"),
  demoSelect: document.querySelector("#demoSelect"),
  profileChoice: document.querySelector("#profileChoice"),
  profileSelect: document.querySelector("#profileSelect"),
  lockedProfile: document.querySelector("#lockedProfile"),
  refreshProfiles: document.querySelector("#refreshProfiles"),
  organizationName: document.querySelector("#organizationName"),
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
  saveIndicator: document.querySelector("#saveIndicator"),
  answersStatus: document.querySelector("#answersStatus"),
  addRoomMenuButton: document.querySelector("#addRoomMenuButton"),
  roomTypeMenu: document.querySelector("#roomTypeMenu"),
  rooms: document.querySelector("#rooms"),
  runSimulation: document.querySelector("#runSimulation"),
  simulationState: document.querySelector("#simulationState"),
  simulationRuns: document.querySelector("#simulationRuns"),
  resultSummary: document.querySelector("#resultSummary"),
};

const hiddenQuestionIds = new Set(["project_name", "rooms"]);

async function api(path, options = {}) {
  const headers = {"Content-Type": "application/json", ...(options.headers || {})};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, {
    headers,
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({detail: response.statusText}));
    throw new Error(toFrenchError(error.detail || response.statusText));
  }
  return response.json();
}

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
  element.classList.toggle("success", Boolean(message) && !isError);
}

function toFrenchError(message) {
  const text = String(message || "");
  const known = {
    "Authentication required.": "Connexion requise.",
    "Invalid email or password.": "Email ou mot de passe invalide.",
    "Password must contain at least 8 characters.": "Le mot de passe doit contenir au moins 8 caractères.",
    "A user with this email already exists.": "Un compte existe déjà avec cet email.",
    "Unknown project.": "Projet introuvable pour votre organisation.",
    "Unknown simulation run.": "Simulation introuvable pour votre organisation.",
    "No answers saved for project": "Aucune réponse sauvegardée pour ce projet.",
    "Organization already exists with a different business profile.": "Cette organisation existe déjà avec un autre profil métier. Revenez à l'étape organisation pour utiliser le profil verrouillé, ou choisissez un autre nom d'organisation.",
    "Unknown business profile.": "Profil métier inconnu.",
  };
  for (const [source, target] of Object.entries(known)) {
    if (text.includes(source)) return target;
  }
  return text || "Une erreur est survenue.";
}

function updateUiState() {
  const isLoggedIn = Boolean(state.user);
  els.loggedOutAccount.hidden = isLoggedIn;
  els.loggedInAccount.hidden = !isLoggedIn;
  els.connectedEmail.textContent = isLoggedIn ? state.user.email : "";
  els.connectedOrganization.textContent = state.organization ? state.organization.name : "";
  els.connectedProfile.textContent = state.organization ? selectedProfile().label : "";
  els.logout.disabled = !isLoggedIn;
  els.register.disabled = isLoggedIn || state.authSubmitting === "register";
  els.login.disabled = isLoggedIn || state.authSubmitting === "login";
  els.organizationStep.hidden = isLoggedIn || state.authStep !== "organization";
  els.credentialsStep.hidden = isLoggedIn || state.authStep !== "credentials";

  if (!isLoggedIn) {
    els.projectSelect.hidden = true;
    els.emptyProjects.hidden = false;
    els.emptyProjects.textContent = "Créez un compte ou connectez-vous pour accéder aux projets";
    els.loadProject.disabled = true;
  }

  const lockedProfile = Boolean(state.organization || state.selectedOrganization?.exists);
  els.profileChoice.hidden = lockedProfile;
  els.lockedProfile.hidden = !lockedProfile;
  els.lockedProfile.textContent = lockedProfile
    ? `Profil : ${selectedProfile().label}`
    : "";
  els.organizationName.disabled = Boolean(state.organization);
  if (state.organization) els.organizationName.value = state.organization.name;
  els.selectedOrganizationSummary.textContent = state.selectedOrganization
    ? `${state.selectedOrganization.name} · ${selectedProfile().label}`
    : "";

  els.projectCreateFields.hidden = !state.projectDraftOpen;
  els.createProject.disabled = !state.organization || !state.projectDraftOpen;
  els.saveAnswers.disabled = !state.project;
  els.runSimulation.disabled = !state.project || !state.answersSaved || state.simulationStatus === "loading";
  els.newProject.disabled = !state.organization;
  els.addRoomMenuButton.disabled = !state.project;
  if (!state.project) els.roomTypeMenu.hidden = true;

  els.saveIndicator.textContent = state.answersSaved ? "✓ Sauvegardé" : "● Non sauvegardé";
  els.saveIndicator.className = `saveIndicator ${state.answersSaved ? "saved" : "unsaved"}`;
  renderProgress();
  renderProjectSummary();
  renderSimulationState();
}

async function loadProfiles() {
  const payload = await api("/business-profiles");
  state.profiles = payload.profiles;
  els.profileSelect.innerHTML = state.profiles
    .map((profile) => `<option value="${profile.id}">${profile.label}</option>`)
    .join("");
  state.profileId = els.profileSelect.value;
  if (state.token) {
    await refreshSession();
  } else {
    await loadQuestionnaire();
  }
  updateUiState();
}

async function refreshSession() {
  try {
    const payload = await api("/auth/me");
    state.user = payload.user;
    els.logout.disabled = false;
    setStatus(els.authStatus, `Connecté : ${state.user.email}`);
    await setOrganizationFromUser();
  } catch {
    state.token = "";
    state.user = null;
    localStorage.removeItem("thermal_saas_token");
    els.logout.disabled = true;
    setStatus(els.authStatus, "Non connecté");
  }
  updateUiState();
}

async function loadQuestionnaire() {
  state.profileId = els.profileSelect.value;
  if (state.selectedOrganization && !state.selectedOrganization.exists) {
    state.selectedOrganization.business_profile_id = state.profileId;
  }
  state.questionnaire = await api(`/business-profiles/${state.profileId}/questionnaire`);
  if (!state.user) state.organization = null;
  state.project = null;
  state.rooms = [defaultRoom()];
  state.answersSaved = false;
  state.simulationRuns = [];
  state.latestReportId = null;
  state.simulationStatus = "idle";
  state.projectDraftOpen = false;
  els.createProject.disabled = true;
  els.saveAnswers.disabled = true;
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
  const payload = await api(`/projects?organization_id=${state.organization.id}`);
  const hasProjects = payload.projects.length > 0;
  els.projectSelect.innerHTML = payload.projects
    .map((project) => `<option value="${project.id}">${project.name} · ${project.customer_name || "Sans client"}</option>`)
    .join("");
  els.projectSelect.hidden = !hasProjects;
  els.emptyProjects.hidden = hasProjects;
  els.emptyProjects.textContent = "Aucun projet pour cette organisation — créez-en un ci-dessus";
  els.loadProject.disabled = !hasProjects;
}

let organizationLookupTimer = null;

function scheduleOrganizationLookup() {
  window.clearTimeout(organizationLookupTimer);
  organizationLookupTimer = window.setTimeout(lookupOrganization, 250);
}

async function lookupOrganization() {
  const name = els.organizationName.value.trim();
  state.selectedOrganization = null;
  if (!name) {
    setStatus(els.organizationLookupStatus, "Entrez le nom de votre organisation.", true);
    updateUiState();
    return;
  }
  try {
    const payload = await api(`/organizations/lookup?name=${encodeURIComponent(name)}`);
    if (payload.exists) {
      state.selectedOrganization = {...payload.organization, exists: true};
      state.profileId = payload.organization.business_profile_id;
      els.profileSelect.value = state.profileId;
      setStatus(
        els.organizationLookupStatus,
        `✓ Organisation trouvée : ${payload.organization.name} — ${payload.organization.business_profile_label}`,
      );
    } else {
      state.selectedOrganization = {
        name,
        business_profile_id: state.profileId,
        exists: false,
      };
      setStatus(els.organizationLookupStatus, "Nouvelle organisation — choisissez son profil métier.");
    }
    await loadQuestionnaire();
  } catch (error) {
    setStatus(els.organizationLookupStatus, error.message, true);
  }
  updateUiState();
}

async function continueToCredentials() {
  await lookupOrganization();
  if (!state.selectedOrganization) return;
  state.authStep = "credentials";
  updateUiState();
}

function backToOrganization() {
  state.authStep = "organization";
  updateUiState();
}

function renderQuestionnaire() {
  els.questionnaireIntro.textContent = `Profil actif : ${selectedProfile().label}`;
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
}

function renderQuestion(question) {
  if (question.type === "select") {
    const options = (question.options || [])
      .map((option) => `<option value="${option.id}">${option.label}</option>`)
      .join("");
    return `<label>${question.label}<select name="${question.id}">${options}</select></label>`;
  }
  const value = question.default ?? "";
  const inputType = question.type === "number" ? "number" : "text";
  return `<label>${question.label}<input name="${question.id}" type="${inputType}" value="${value}"></label>`;
}

const positionOptions = {
  house: [
    ["single_storey_house", "Maison de plain-pied"],
    ["multi_storey_house", "Maison avec étage"],
  ],
  apartment: [
    ["apartment_ground_floor", "Appartement en rez-de-chaussée"],
    ["apartment_middle_floor", "Appartement en étage intermédiaire"],
    ["apartment_top_floor", "Appartement au dernier étage"],
    ["apartment_ground_top_floor", "Appartement en rez-de-chaussée directement sous toiture"],
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
  setField("city", "Bordeaux");
  setField("postal_code", "33000");
  setField("dwelling_type", "house");
  setField("position_id", "single_storey_house");
  setField("period_id", "2001_2012_good_insulation");
}

function markUnsaved() {
  if (!state.project) return;
  state.answersSaved = false;
  state.simulationStatus = state.simulationRuns.length ? "success" : "idle";
  updateUiState();
}

function setField(name, value) {
  const field = els.questionnaireForm.elements.namedItem(name);
  if (field) field.value = value;
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
    living: ["Salon", "living", 24, 4.0, 5.0],
    bedroom: ["Chambre", "bedroom", 12, 1.5, 3.5],
    kitchen: ["Cuisine", "kitchen", 10, 1.2, 3.2],
    bathroom: ["Salle de bain", "bathroom", 6, 0.6, 2.5],
    toilet: ["Toilettes", "utility", 2, 0.3, 1.4],
    office: ["Bureau", "office", 9, 1.2, 3.0],
    corridor: ["Couloir", "corridor", 6, 0.0, 2.5],
    utility: ["Buanderie", "utility", 5, 0.4, 2.2],
    other: ["Pièce", "other", 15, 1.2, 4.0],
  };
  const [name, type, area, windowArea, wallLength] = presets[kind] || presets.other;
  return {
    name,
    type,
    floor_area_m2: area,
    height_m: 2.5,
    orientation: "S",
    window_area_m2: windowArea,
    wall_length_m: wallLength,
    exterior_contact: "exterior",
    mask_factor: 1,
    has_roof: true,
    has_ground_floor: true,
  };
}

function roomFieldVisible(field) {
  if (["name", "type", "floor_area_m2", "height_m"].includes(field)) return true;
  if (state.profileId === "heat_pump_seller") return false;
  if (["roof_insulation_seller", "reflective_roof_seller"].includes(state.profileId)) {
    return ["has_roof", "orientation", "wall_length_m"].includes(field);
  }
  return ["orientation", "window_area_m2", "wall_length_m", "mask_factor"].includes(field);
}

function renderRoomField(field, html) {
  return roomFieldVisible(field) ? html : "";
}

function renderRooms() {
  els.rooms.innerHTML = state.rooms.map((room, index) => `
    <div class="room" data-room-index="${index}">
      <div class="roomTitle">
        <h3>Pièce ${index + 1}</h3>
        <button class="removeRoom" type="button" data-remove-room="${index}">Retirer</button>
      </div>
      ${renderRoomField("name", `<label>Nom<input data-room-field="name" value="${room.name}"></label>`)}
      ${renderRoomField("type", `<label>Type
        <select data-room-field="type">
          ${option("living", "Salon / séjour", room.type)}
          ${option("bedroom", "Chambre", room.type)}
          ${option("kitchen", "Cuisine", room.type)}
          ${option("bathroom", "Salle de bain", room.type)}
          ${option("office", "Bureau", room.type)}
          ${option("corridor", "Couloir / entrée", room.type)}
          ${option("utility", "Toilettes / buanderie", room.type)}
          ${option("other", "Autre", room.type)}
        </select>
      </label>`)}
      ${renderRoomField("floor_area_m2", `<label>Surface m²<input data-room-field="floor_area_m2" type="number" value="${room.floor_area_m2}"></label>`)}
      ${renderRoomField("height_m", `<label>Hauteur m<input data-room-field="height_m" type="number" value="${room.height_m}"></label>`)}
      ${renderRoomField("orientation", `<label>Orientation
        <select data-room-field="orientation">
          ${["N", "E", "S", "W", "SE", "SW"].map((value) => option(value, value, room.orientation)).join("")}
        </select>
      </label>`)}
      ${renderRoomField("window_area_m2", `<label>Vitrage m²<input data-room-field="window_area_m2" type="number" value="${room.window_area_m2}"></label>`)}
      ${renderRoomField("wall_length_m", `<label>Longueur façade m<input data-room-field="wall_length_m" type="number" value="${room.wall_length_m}"></label>`)}
      ${renderRoomField("mask_factor", `<label>Masque solaire
        <select data-room-field="mask_factor">
          ${option("1", "Aucun masque", String(room.mask_factor ?? 1))}
          ${option("0.85", "Masque léger", String(room.mask_factor ?? 1))}
          ${option("0.65", "Masque moyen", String(room.mask_factor ?? 1))}
          ${option("0.4", "Masque fort", String(room.mask_factor ?? 1))}
        </select>
      </label>`)}
      ${renderRoomField("has_roof", `<label>Sous toiture
        <select data-room-field="has_roof">
          ${option("true", "Oui", String(room.has_roof))}
          ${option("false", "Non", String(room.has_roof))}
        </select>
      </label>`)}
    </div>
  `).join("");
}

function option(value, label, selected) {
  return `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`;
}

function syncRoomsFromDom() {
  state.rooms = [...document.querySelectorAll(".room")].map((roomElement) => {
    const value = (field, fallback) => {
      const fieldElement = roomElement.querySelector(`[data-room-field="${field}"]`);
      return fieldElement ? fieldElement.value : fallback;
    };
    return {
      name: value("name", "Pièce"),
      type: value("type", "living"),
      floor_area_m2: Number(value("floor_area_m2", 20)),
      height_m: Number(value("height_m", 2.5)),
      has_roof: value("has_roof", "true") === "true",
      has_ground_floor: true,
      exterior_contact: "exterior",
      facades: [{
        orientation: value("orientation", "S"),
        window_area_m2: Number(value("window_area_m2", 0)),
        wall_length_m: Number(value("wall_length_m", 4)),
        mask_factor: Number(value("mask_factor", 1)),
      }],
    };
  });
}

function collectAnswers() {
  syncRoomsFromDom();
  const formData = new FormData(els.questionnaireForm);
  const answers = Object.fromEntries(formData.entries());
  answers.project_name = els.projectName.value;
  answers.rooms = state.rooms;
  for (const key of ["heating_setpoint_c", "cooling_setpoint_c"]) {
    if (answers[key] !== undefined && answers[key] !== "") answers[key] = Number(answers[key]);
  }
  return answers;
}

function selectedProfile() {
  return state.profiles.find((profile) => profile.id === state.profileId) || {label: state.profileId};
}

async function register() {
  state.authSubmitting = "register";
  updateUiState();
  try {
    if (!state.selectedOrganization) await continueToCredentials();
    const payload = await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email: els.email.value,
        password: els.password.value,
        organization_name: state.selectedOrganization.name,
        business_profile_id: state.profileId,
      }),
    });
    setSession(payload);
    await setOrganizationFromUser(payload.organization);
  } catch (error) {
    setStatus(els.authStatus, error.message, true);
  } finally {
    state.authSubmitting = "";
    updateUiState();
  }
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
        organization_name: state.selectedOrganization?.name || els.organizationName.value,
      }),
    });
    setSession(payload);
    state.profileId = payload.organization.business_profile_id;
    els.profileSelect.value = state.profileId;
    await loadQuestionnaire();
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
  state.authStep = "organization";
  state.authSubmitting = "";
  localStorage.removeItem("thermal_saas_token");
  els.logout.disabled = true;
  els.createProject.disabled = true;
  els.saveAnswers.disabled = true;
  els.runSimulation.disabled = true;
  els.projectSelect.innerHTML = "";
  els.simulationRuns.innerHTML = "";
  els.resultSummary.innerHTML = "";
  setStatus(els.authStatus, "Déconnecté");
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
  state.authStep = "credentials";
  localStorage.setItem("thermal_saas_token", state.token);
  els.logout.disabled = false;
  setStatus(els.authStatus, `Connecté : ${state.user.email}`);
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
    setStatus(els.authStatus, "Aucune organisation associée à ce compte.", true);
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
  setStatus(els.authStatus, `Connecté : ${state.user.email}`);
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
    state.simulationRuns = [];
    state.latestReportId = null;
    state.simulationStatus = "idle";
    state.projectDraftOpen = false;
    els.saveAnswers.disabled = false;
    els.runSimulation.disabled = true;
    await refreshProjects();
    setStatus(els.projectStatus, `✓ Projet créé : ${state.project.name} — ${state.project.customer_name || "Sans client"}`);
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
  state.simulationRuns = [];
  state.latestReportId = null;
  state.simulationStatus = "idle";
  state.projectDraftOpen = true;
  state.rooms = [defaultRoom()];
  els.projectName.value = "Maison client";
  els.customerName.value = "Client test";
  els.resultSummary.innerHTML = "";
  els.simulationRuns.innerHTML = "";
  setStatus(els.projectStatus, "Nouveau projet prêt à créer.");
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
  els.saveAnswers.disabled = false;
  state.answersSaved = Boolean(payload.latest_answers);
  state.simulationRuns = payload.simulation_runs;
  state.latestReportId = payload.simulation_runs.length ? payload.simulation_runs[payload.simulation_runs.length - 1].id : null;
  state.simulationStatus = payload.simulation_runs.length ? "success" : "idle";
  els.runSimulation.disabled = !state.answersSaved;
  if (payload.latest_answers) {
    applyAnswers(payload.latest_answers.answers);
    setStatus(els.answersStatus, `Dernières réponses : version ${payload.latest_answers.version}`);
  }
  renderSimulationRuns(payload.simulation_runs);
  await renderLatestSummary(payload.simulation_runs);
  setStatus(els.projectStatus, `Projet chargé : ${state.project.id}`);
  updateUiState();
}

function applyAnswers(answers) {
  els.projectName.value = answers.project_name || state.project?.name || els.projectName.value;
  for (const [key, value] of Object.entries(answers)) {
    if (key === "rooms") continue;
    setField(key, value);
  }
  syncPositionOptions();
  if (answers.rooms) {
    state.rooms = answers.rooms.map((room) => ({
      name: room.name,
      type: room.type,
      floor_area_m2: room.floor_area_m2,
      height_m: room.height_m,
      orientation: room.facades?.[0]?.orientation || "S",
      window_area_m2: room.facades?.[0]?.window_area_m2 || 0,
      wall_length_m: room.facades?.[0]?.wall_length_m || 4,
      has_roof: Boolean(room.has_roof),
    }));
    renderRooms();
  }
  updateUiState();
}

async function saveAnswers() {
  els.saveAnswers.disabled = true;
  try {
    const saved = await api(`/projects/${state.project.id}/answers`, {
      method: "POST",
      body: JSON.stringify({answers: collectAnswers()}),
    });
    state.answersSaved = true;
    state.simulationStatus = state.simulationRuns.length ? "success" : "idle";
    state.lastSimulationError = "";
    setStatus(els.answersStatus, `Réponses sauvegardées : version ${saved.version}`);
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
    state.latestReportId = batch.simulation_runs.length ? batch.simulation_runs[batch.simulation_runs.length - 1].id : null;
    state.simulationStatus = "success";
    renderSimulationRuns(batch.simulation_runs);
    await renderLatestSummary(batch.simulation_runs);
    setStatus(els.answersStatus, "Simulation terminée");
  } catch (error) {
    state.simulationStatus = "error";
    state.lastSimulationError = error.message;
    setStatus(els.answersStatus, error.message, true);
  } finally {
    updateUiState();
  }
}

function renderSimulationRuns(runs) {
  state.simulationRuns = runs;
  if (!runs.length) {
    els.simulationRuns.innerHTML = "";
    return;
  }
  els.simulationRuns.innerHTML = runs.map((run) => `
    <div class="run">
      <div>
        <strong>${run.adaptation_id} · ${run.season} · ${run.role}</strong>
        <p>${run.status} · ${run.id}</p>
      </div>
      <button type="button" data-open-report="${run.id}">Rapport HTML</button>
    </div>
  `).join("");
}

async function openReport(simulationRunId) {
  const reportWindow = window.open("", "_blank");
  if (!reportWindow) {
    throw new Error("Le navigateur a bloqué l'ouverture du rapport.");
  }
  reportWindow.document.write("<p>Chargement du rapport...</p>");
  const response = await fetch(`/simulation-runs/${simulationRunId}/report-html`, {
    headers: {Authorization: `Bearer ${state.token}`},
  });
  if (!response.ok) {
    reportWindow.close();
    throw new Error("Rapport inaccessible.");
  }
  const html = await response.text();
  reportWindow.document.open();
  reportWindow.document.write(html);
  reportWindow.document.close();
}

async function renderLatestSummary(runs) {
  if (!runs.length) {
    els.resultSummary.innerHTML = "";
    return;
  }
  const latestRun = runs[runs.length - 1];
  state.latestReportId = latestRun.id;
  const payload = await api(`/simulation-runs/${latestRun.id}`);
  const summary = payload.result.comparison.summary;
  const headline = summary.headline_metrics;
  const energy = summary.energy_savings;
  els.resultSummary.innerHTML = `
    <div class="metric"><span>Économie électricité</span><strong>${formatNumber(energy.electricity_saved_kwh)} kWh</strong></div>
    <div class="metric"><span>Économie estimée</span><strong>${formatNumber(energy.cost_saved_eur)} €</strong></div>
    <div class="metric"><span>CO₂ évité</span><strong>${formatNumber(energy.co2_saved_kg)} kg</strong></div>
    <div class="metric"><span>Réduction température max</span><strong>${formatNumber(headline.max_temperature_reduction_c)} °C</strong></div>
    <div class="metric"><span>Inconfort chaud évité</span><strong>${formatNumber(headline.hot_degree_hours_reduced)} °C·h</strong></div>
    <div class="metric"><span>Inconfort froid évité</span><strong>${formatNumber(headline.cold_degree_hours_reduced)} °C·h</strong></div>
  `;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("fr-FR", {maximumFractionDigits: 2});
}

function renderProgress() {
  const completed = {
    account: Boolean(state.user),
    organization: Boolean(state.organization),
    project: Boolean(state.project),
    dwelling: Boolean(state.answersSaved),
    simulation: state.simulationRuns.length > 0,
  };
  const order = ["account", "organization", "project", "dwelling", "simulation"];
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
  const latest = state.simulationRuns.length
    ? `Dernière simulation : ${formatDate(state.simulationRuns[state.simulationRuns.length - 1].created_at)} ✓`
    : "Dernière simulation : aucune";
  const city = getField("city", "Bordeaux");
  const postalCode = getField("postal_code", "33000");
  els.projectSummary.hidden = false;
  els.projectSummary.innerHTML = `
    <div class="projectSummaryTitle">📁 ${state.project.name} — ${state.project.customer_name || "Sans client"}</div>
    <div class="projectSummaryMeta">Profil : ${selectedProfile().label} | ${state.rooms.length} pièce${state.rooms.length > 1 ? "s" : ""} | ${postalCode} ${city}</div>
    <div class="projectSummaryMeta">${latest}</div>
    <div class="projectSummaryActions">
      <button type="button" ${state.latestReportId ? `data-open-report="${state.latestReportId}"` : "disabled"}>Voir le rapport HTML</button>
    </div>
  `;
}

function renderSimulationState() {
  els.runSimulation.textContent = state.simulationStatus === "loading"
    ? "⏳ Simulation en cours…"
    : "Lancer simulation";
  if (state.simulationStatus === "loading") {
    els.simulationState.className = "stateBox";
    els.simulationState.textContent = "⏳ Simulation en cours…";
  } else if (state.simulationStatus === "success" && state.simulationRuns.length) {
    const latestRun = state.simulationRuns[state.simulationRuns.length - 1];
    els.simulationState.className = "stateBox success";
    els.simulationState.textContent = `✓ Simulation terminée le ${formatDate(latestRun.created_at)} — voir la synthèse`;
  } else if (state.simulationStatus === "error") {
    els.simulationState.className = "stateBox error";
    els.simulationState.innerHTML = `${state.lastSimulationError || "Erreur de simulation."} <strong>Corrigez les informations puis cliquez sur Réessayer.</strong>`;
    els.runSimulation.textContent = "Réessayer";
  } else {
    els.simulationState.className = "stateBox";
    els.simulationState.textContent = "Aucune simulation lancée — remplissez le questionnaire puis cliquez sur Lancer simulation";
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
  state.authStep = "organization";
  state.selectedOrganization = null;
  els.email.value = `demo.${profileId}.${suffix}@thermaltwin.local`;
  els.password.value = "password123";
  els.organizationName.value = demoOrganizationName(demoId, suffix);
  els.projectName.value = demoProjectName(demoId);
  els.customerName.value = "Client demo";
  loadQuestionnaire().then(() => {
    const answers = demoAnswers(demoId);
    state.pendingDemoAnswers = answers;
    for (const [key, value] of Object.entries(answers)) {
      if (key !== "rooms") setField(key, value);
    }
    state.rooms = answers.rooms.map((room) => ({
      name: room.name,
      type: room.type,
      floor_area_m2: room.floor_area_m2,
      height_m: room.height_m,
      orientation: room.facades?.[0]?.orientation || "S",
      window_area_m2: room.facades?.[0]?.window_area_m2 || 0,
      wall_length_m: room.facades?.[0]?.wall_length_m || 4,
      has_roof: Boolean(room.has_roof),
    }));
    renderRooms();
    state.answersSaved = false;
    setStatus(els.authStatus, "Démo préremplie — cliquez sur Continuer puis créez le compte.");
    updateUiState();
  });
}

function demoOrganizationName(demoId, suffix) {
  if (demoId === "heat_pump_seller") return `Demo PAC Pro ${suffix}`;
  if (demoId === "solar_protection_seller") return `Demo Stores Pro ${suffix}`;
  if (demoId === "window_seller") return `Demo Fenetres Pro ${suffix}`;
  if (demoId === "roof_insulation_seller") return `Demo Isolation Toiture ${suffix}`;
  return `Demo Peinture Toiture ${suffix}`;
}

function demoProjectName(demoId) {
  if (demoId === "heat_pump_seller") return "Maison demo PAC";
  if (demoId === "solar_protection_seller") return "Maison demo protection solaire";
  if (demoId === "window_seller") return "Maison demo fenetres";
  if (demoId === "roof_insulation_seller") return "Maison demo isolation toiture";
  return "Maison demo peinture toiture";
}

function demoAnswers(demoId) {
  const common = {
    city: "Bordeaux",
    postal_code: "33000",
    dwelling_type: "house",
    position_id: "single_storey_house",
    period_id: "2001_2012_good_insulation",
    rooms: [
      {
        name: "Salon",
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
      attic_ventilation_id: "limited",
    };
  }
  return {
    ...common,
    adaptation_id: "reflective_roof",
    roof_insulation_id: "standard",
    roof_color_id: "dark",
    attic_ventilation_id: "limited",
  };
}

els.refreshProfiles.addEventListener("click", loadProfiles);
els.register.addEventListener("click", register);
els.login.addEventListener("click", login);
els.logout.addEventListener("click", logout);
els.profileSelect.addEventListener("change", () => {
  state.profileId = els.profileSelect.value;
  if (state.selectedOrganization && !state.selectedOrganization.exists) {
    state.selectedOrganization.business_profile_id = state.profileId;
  }
  loadQuestionnaire().catch((error) => setStatus(els.authStatus, error.message, true));
});
els.organizationName.addEventListener("input", scheduleOrganizationLookup);
els.organizationName.addEventListener("focus", scheduleOrganizationLookup);
els.continueToCredentials.addEventListener("click", () => continueToCredentials().catch((error) => setStatus(els.organizationLookupStatus, error.message, true)));
els.backToOrganization.addEventListener("click", backToOrganization);
els.demoSelect.addEventListener("change", (event) => applyDemo(event.target.value));
els.createProject.addEventListener("click", createProject);
els.newProject.addEventListener("click", startNewProject);
els.loadProject.addEventListener("click", () => loadProject().catch((error) => setStatus(els.projectStatus, error.message, true)));
els.saveAnswers.addEventListener("click", saveAnswers);
els.runSimulation.addEventListener("click", runSimulation);
els.questionnaireForm.addEventListener("input", markUnsaved);
els.questionnaireForm.addEventListener("change", (event) => {
  if (event.target.name === "dwelling_type") syncPositionOptions();
  markUnsaved();
});
els.rooms.addEventListener("input", markUnsaved);
els.projectName.addEventListener("input", markUnsaved);
els.addRoomMenuButton.addEventListener("click", () => {
  els.roomTypeMenu.hidden = !els.roomTypeMenu.hidden;
});
els.roomTypeMenu.addEventListener("click", (event) => {
  const roomType = event.target.dataset.roomType;
  if (!roomType) return;
  syncRoomsFromDom();
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
  const simulationRunId = event.target.dataset.openReport;
  if (!simulationRunId) return;
  openReport(simulationRunId).catch((error) => setStatus(els.answersStatus, error.message, true));
});
els.projectSummary.addEventListener("click", (event) => {
  const simulationRunId = event.target.dataset.openReport;
  if (!simulationRunId) return;
  openReport(simulationRunId).catch((error) => setStatus(els.answersStatus, error.message, true));
});

loadProfiles().catch((error) => setStatus(els.authStatus, error.message, true));
