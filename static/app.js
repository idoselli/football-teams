const presetPlayers = window.APP_PLAYERS || [];

const state = {
  selectedIds: new Set(),
  guestPlayers: [],
  nextGuestId: 1,
  latestSuggestions: [],
};

const playersGrid = document.getElementById("players-grid");
const guestForm = document.getElementById("guest-form");
const guestNameInput = document.getElementById("guest-name");
const guestSkillInput = document.getElementById("guest-skill");
const guestList = document.getElementById("guest-list");
const selectionPill = document.getElementById("selection-pill");
const helperText = document.getElementById("helper-text");
const generateButton = document.getElementById("generate-button");
const resultsGrid = document.getElementById("results-grid");
const copyAllButton = document.getElementById("copy-all-button");

function formatSkill(skill) {
  const numericSkill = Number(skill);
  if (Number.isInteger(numericSkill)) {
    return String(numericSkill);
  }
  return numericSkill.toFixed(1);
}

function allPlayers() {
  return [...presetPlayers, ...state.guestPlayers];
}

function selectedPlayers() {
  return allPlayers().filter((player) => state.selectedIds.has(player.id));
}

function renderPlayers() {
  playersGrid.innerHTML = "";

  allPlayers().forEach((player) => {
    const label = document.createElement("label");
    label.className = "player-card";
    label.dataset.playerId = String(player.id);
    label.classList.toggle("selected", state.selectedIds.has(player.id));

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = String(player.id);
    input.checked = state.selectedIds.has(player.id);
    input.addEventListener("change", () => togglePlayer(player.id, label, input.checked));

    const meta = document.createElement("div");
    meta.className = "player-meta";

    const name = document.createElement("span");
    name.className = "player-name";
    name.textContent = player.name;
    name.setAttribute("dir", "auto");

    const skill = document.createElement("span");
    skill.className = "skill-badge";
    skill.textContent = `Skill ${formatSkill(player.skill)}/10`;

    meta.append(name, skill);

    if (player.source === "guest") {
      const guestTag = document.createElement("span");
      guestTag.className = "guest-tag";
      guestTag.textContent = "Guest";
      meta.append(guestTag);
    }

    label.append(input, meta);
    playersGrid.append(label);
  });
}

function renderGuests() {
  guestList.innerHTML = "";

  if (state.guestPlayers.length === 0) {
    guestList.innerHTML = `
      <article class="empty-mini-state">
        <p>No guest players yet.</p>
      </article>
    `;
    return;
  }

  state.guestPlayers.forEach((player) => {
    const card = document.createElement("article");
    card.className = "guest-item";
    card.innerHTML = `
      <div>
        <strong dir="auto">${player.name}</strong>
        <p>Skill ${formatSkill(player.skill)}/10</p>
      </div>
      <button class="ghost-button" type="button" data-remove-id="${player.id}">Remove</button>
    `;

    const removeButton = card.querySelector("button");
    removeButton.addEventListener("click", () => removeGuest(player.id));
    guestList.append(card);
  });
}

function togglePlayer(playerId, label, checked) {
  if (checked && state.selectedIds.size >= 15) {
    const checkbox = label.querySelector("input");
    checkbox.checked = false;
    setHelper("You can choose up to 15 players.", true);
    return;
  }

  if (checked) {
    state.selectedIds.add(playerId);
    label.classList.add("selected");
  } else {
    state.selectedIds.delete(playerId);
    label.classList.remove("selected");
  }

  updateSelectionStatus();
}

function updateSelectionStatus() {
  const count = state.selectedIds.size;
  selectionPill.textContent = `${count} selected`;

  if (count < 12) {
    setHelper("Select at least 12 players to unlock team suggestions.", false);
    generateButton.disabled = true;
    return;
  }

  setHelper("Ready to generate three balanced team combinations.", false);
  generateButton.disabled = false;
}

function setHelper(message, warning) {
  helperText.textContent = message;
  helperText.classList.toggle("warning", warning);
}

function addGuest(event) {
  event.preventDefault();

  const name = guestNameInput.value.trim();
  const skill = Number(guestSkillInput.value);

  if (!name) {
    setHelper("Please enter a guest name.", true);
    guestNameInput.focus();
    return;
  }

  if (Number.isNaN(skill) || skill < 1 || skill > 10) {
    setHelper("Guest skill must be between 1 and 10.", true);
    guestSkillInput.focus();
    return;
  }

  const player = {
    id: `guest-${state.nextGuestId}`,
    name,
    skill: Math.round(skill * 10) / 10,
    source: "guest",
  };

  state.nextGuestId += 1;
  state.guestPlayers.push(player);

  if (state.selectedIds.size < 15) {
    state.selectedIds.add(player.id);
  }

  guestForm.reset();
  renderPlayers();
  renderGuests();
  updateSelectionStatus();
  setHelper(`Added ${name}.`, false);
  guestNameInput.focus();
}

function removeGuest(guestId) {
  state.guestPlayers = state.guestPlayers.filter((player) => player.id !== guestId);
  state.selectedIds.delete(guestId);
  renderPlayers();
  renderGuests();
  updateSelectionStatus();
}

function renderEmptyState(message) {
  state.latestSuggestions = [];
  copyAllButton.disabled = true;
  resultsGrid.innerHTML = `
    <article class="empty-state">
      <h3>${message}</h3>
      <p>Adjust the selection above and try again.</p>
    </article>
  `;
}

function buildCopyText(suggestion) {
  const lines = [suggestion.label];

  suggestion.teams.forEach((team) => {
    const playerLine = team.players.map((player) => player.name).join(", ");
    lines.push(`${team.name} (Avg ${formatSkill(team.average_skill)}): ${playerLine}`);
  });

  return lines.join("\n");
}

function buildAllSuggestionsCopyText() {
  return state.latestSuggestions.map((suggestion) => buildCopyText(suggestion)).join("\n\n");
}

function fallbackCopyText(text) {
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "absolute";
  textArea.style.left = "-9999px";
  document.body.append(textArea);
  textArea.select();
  document.execCommand("copy");
  textArea.remove();
}

function flashCopyButton(stateName, label) {
  copyAllButton.classList.remove("copying", "copied");
  if (stateName) {
    copyAllButton.classList.add(stateName);
  }
  copyAllButton.textContent = label;
}

async function copyAllSuggestions() {
  if (!state.latestSuggestions.length) {
    return;
  }

  const text = buildAllSuggestionsCopyText();

  try {
    flashCopyButton("copying", "Copying...");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      fallbackCopyText(text);
    }
    flashCopyButton("copied", "Copied");
    setHelper("Copied all options to the clipboard.", false);
    window.setTimeout(() => {
      flashCopyButton("", "Copy All Options");
    }, 1400);
  } catch (error) {
    flashCopyButton("", "Copy All Options");
    setHelper("Copy failed on this device. You can try again or use a modern browser.", true);
  }
}

function renderSuggestions(suggestions) {
  state.latestSuggestions = suggestions;
  copyAllButton.disabled = false;
  flashCopyButton("", "Copy All Options");
  resultsGrid.innerHTML = "";

  suggestions.forEach((suggestion) => {
    const card = document.createElement("article");
    card.className = "result-card";

    const teamsMarkup = suggestion.teams
      .map(
        (team) => `
          <section class="team-card">
            <h4>${team.name}</h4>
            <p class="team-meta">${team.size} players | Avg skill ${team.average_skill}</p>
            <ul class="team-list">
              ${team.players
                .map(
                  (player) => `
                    <li class="team-player">
                      <strong dir="auto">${player.name}</strong>
                      <small>Skill ${formatSkill(player.skill)}</small>
                    </li>
                  `
                )
                .join("")}
            </ul>
          </section>
        `
      )
      .join("");

    card.innerHTML = `
      <div class="result-header">
        <div>
          <h3>${suggestion.label}</h3>
          <p class="team-meta">Team average spread: ${suggestion.imbalance}</p>
        </div>
      </div>
      <div class="teams-stack">${teamsMarkup}</div>
    `;
    resultsGrid.append(card);
  });
}

async function generateTeams() {
  const roster = selectedPlayers();

  if (roster.length < 12 || roster.length > 15) {
    setHelper("Please choose between 12 and 15 players.", true);
    return;
  }

  generateButton.disabled = true;
  generateButton.textContent = "Generating...";
  setHelper("Finding balanced combinations with better variation across all three options.", false);

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        selected_players: roster,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Unable to generate teams.");
    }

    if (!data.suggestions || data.suggestions.length === 0) {
      renderEmptyState("No balanced suggestions found");
      return;
    }

    renderSuggestions(data.suggestions);
    setHelper("Generated three balanced options with added variation. Copy any option for your group chat.", false);
  } catch (error) {
    renderEmptyState("Could not generate teams");
    setHelper(error.message, true);
  } finally {
    generateButton.textContent = "Generate Balanced Teams";
    generateButton.disabled = false;
  }
}

guestForm.addEventListener("submit", addGuest);
generateButton.addEventListener("click", generateTeams);
copyAllButton.addEventListener("click", copyAllSuggestions);

renderPlayers();
renderGuests();
updateSelectionStatus();
