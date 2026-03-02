const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const PROTEINS = [
  { value: 'Chicken',    emoji: '🍗', group: 'meat' },
  { value: 'Beef',       emoji: '🥩', group: 'meat' },
  { value: 'Pork',       emoji: '🐷', group: 'meat' },
  { value: 'Turkey',     emoji: '🦃', group: 'meat' },
  { value: 'Fish',       emoji: '🐟', group: 'meat' },
  { value: 'Seafood',    emoji: '🦐', group: 'meat' },
  { value: 'Lamb',       emoji: '🐑', group: 'meat' },
  { value: 'Tofu',       emoji: '🫘', group: 'veg' },
  { value: 'Eggs',       emoji: '🥚', group: 'veg' },
  { value: 'Beans',      emoji: '🫘', group: 'veg' },
  { value: 'Lentils',    emoji: '🌱', group: 'veg' },
  { value: 'Tempeh',     emoji: '🌿', group: 'veg' },
  { value: 'Cheese',     emoji: '🧀', group: 'veg' },
  { value: 'Vegetarian', emoji: '🥦', group: 'veg' },
];

function proteinEmoji(value) {
  return PROTEINS.find(p => p.value === value)?.emoji || '';
}

function app() {
  return {
    // ── Navigation ──────────────────────────────────────────
    tabs: [
      { id: 'week',     label: "This Week" },
      { id: 'library',  label: "Meal Library" },
      { id: 'history',  label: "Past Weeks" },
      { id: 'settings', label: "Settings" },
    ],
    activeTab: 'week',

    // ── Data ────────────────────────────────────────────────
    currentPlan: null,
    pastPlans: [],
    meals: [],
    settings: { gym_days: [], eat_out_days: [], ai_provider: 'anthropic' },

    // ── AI ───────────────────────────────────────────────────
    aiLoading: false,
    aiError: null,
    aiSuccess: false,
    aiConfigured: null,   // null = unknown, true = ready, false = not configured

    // ── Settings UI ─────────────────────────────────────────
    settingsSaving: false,
    settingsSaved: false,

    // ── Day editor ──────────────────────────────────────────
    dayEditorOpen: false,
    editingDay: null,
    editDayForm: { day_type: 'skip', meal_id: null, meal_name: '', custom_name: '', notes: '' },
    mealPickerSearch: '',
    daySaving: false,

    // ── Meal editor ─────────────────────────────────────────
    mealEditorOpen: false,
    editingMeal: null,
    mealForm: { name: '', meal_type: 'home_cooked', notes: '', recipe_url: '', has_leftovers: false, easy_to_make: false, shared_ingredients: '', protein: '' },
    mealSearch: '',
    mealSaving: false,
    proteins: PROTEINS,

    // ── History ─────────────────────────────────────────────
    expandedPlan: null,
    historyDetails: {},

    // ── Init ────────────────────────────────────────────────
    async init() {
      await Promise.all([
        this.loadCurrentPlan(),
        this.loadMeals(),
        this.loadSettings(),
        this.loadPastPlans(),
        this.loadAIStatus(),
      ]);
    },

    // ── API helpers ─────────────────────────────────────────
    async api(method, path, body) {
      const opts = { method, headers: { 'Content-Type': 'application/json' } };
      if (body !== undefined) opts.body = JSON.stringify(body);
      const res = await fetch('/api' + path, opts);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
      }
      if (res.status === 204) return null;
      return res.json();
    },

    // ── Loaders ─────────────────────────────────────────────
    async loadCurrentPlan() {
      this.currentPlan = await this.api('GET', '/plans/current');
    },

    async loadMeals() {
      this.meals = await this.api('GET', '/meals?active_only=true');
    },

    async loadSettings() {
      this.settings = await this.api('GET', '/settings');
    },

    async loadPastPlans() {
      const all = await this.api('GET', '/plans');
      const currentMonday = this.currentPlan?.week_start;
      this.pastPlans = all.filter(p => p.week_start !== currentMonday);
    },

    async loadAIStatus() {
      try {
        const status = await this.api('GET', '/ai/status');
        this.aiConfigured = status.configured;
      } catch {
        this.aiConfigured = false;
      }
    },

    // ── Week helpers ─────────────────────────────────────────
    weekLabel(weekStart) {
      if (!weekStart) return '';
      const d = new Date(weekStart + 'T00:00:00');
      const end = new Date(d);
      end.setDate(end.getDate() + 6);
      const fmt = (dt) => dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      return `Week of ${fmt(d)} – ${fmt(end)}`;
    },

    sortedDays(plan) {
      if (!plan || !plan.days) return [];
      const days = [...plan.days].sort((a, b) => a.day_of_week - b.day_of_week);
      // ensure all 7 days exist as stubs
      const map = Object.fromEntries(days.map(d => [d.day_of_week, d]));
      return Array.from({ length: 7 }, (_, i) => map[i] || { day_of_week: i, day_type: 'skip', meal: null, notes: '', custom_name: '' });
    },

    dayName(dow) {
      return DAY_NAMES[dow] || '';
    },

    dayIcon(day) {
      if (!day) return '';
      if (day.day_type === 'home_cooked') {
        if (this.settings.gym_days.includes(day.day_of_week)) return '🏋️';
        return '🍳';
      }
      if (day.day_type === 'eat_out') return '🍽️';
      return '—';
    },

    dayCardClass(day) {
      if (!day) return 'border-gray-200';
      if (day.day_type === 'home_cooked') {
        if (this.settings.gym_days.includes(day.day_of_week)) return 'border-yellow-300 bg-yellow-50';
        return 'border-green-300';
      }
      if (day.day_type === 'eat_out') return 'border-blue-300';
      return 'border-gray-200 opacity-60';
    },

    dayShortLabel(day) {
      if (!day) return '—';
      if (day.day_type === 'home_cooked') return day.meal ? day.meal.name : 'Home cooked';
      if (day.day_type === 'eat_out') return day.custom_name || 'Eat out';
      return '—';
    },

    // ── Meal helpers ─────────────────────────────────────────
    filteredMeals() {
      const q = this.mealSearch.toLowerCase();
      return this.meals.filter(m => !q || m.name.toLowerCase().includes(q));
    },

    filteredPickerMeals() {
      const q = this.mealPickerSearch.toLowerCase();
      return this.meals
        .filter(m => m.meal_type === 'home_cooked' || m.meal_type === 'other')
        .filter(m => !q || m.name.toLowerCase().includes(q));
    },

    mealTypeLabel(t) {
      return { home_cooked: 'Home cooked', eat_out: 'Eat out', other: 'Other' }[t] || t;
    },

    mealTypeClass(t) {
      return {
        home_cooked: 'bg-green-100 text-green-700',
        eat_out: 'bg-blue-100 text-blue-700',
        other: 'bg-gray-100 text-gray-600',
      }[t] || 'bg-gray-100 text-gray-600';
    },

    proteinChipClass(group) {
      return group === 'meat'
        ? 'bg-red-100 text-red-700'
        : 'bg-teal-100 text-teal-700';
    },

    proteinInfo(value) {
      return PROTEINS.find(p => p.value === value) || null;
    },

    // ── Day editor ──────────────────────────────────────────
    openDayEditor(day) {
      this.editingDay = day;
      this.mealPickerSearch = '';
      this.editDayForm = {
        day_type: day.day_type || 'skip',
        meal_id: day.meal_id || null,
        meal_name: day.meal ? day.meal.name : '',
        custom_name: day.custom_name || '',
        notes: day.notes || '',
      };
      this.dayEditorOpen = true;
    },

    async saveDay() {
      if (!this.currentPlan || !this.editingDay) return;
      this.daySaving = true;
      try {
        const dow = this.editingDay.day_of_week;
        const updated = await this.api(
          'PUT',
          `/plans/${this.currentPlan.id}/days/${dow}`,
          {
            day_type: this.editDayForm.day_type,
            meal_id: this.editDayForm.day_type === 'home_cooked' ? this.editDayForm.meal_id : null,
            custom_name: this.editDayForm.custom_name,
            notes: this.editDayForm.notes,
          }
        );
        // update the local plan
        const idx = this.currentPlan.days.findIndex(d => d.day_of_week === dow);
        if (idx >= 0) {
          this.currentPlan.days[idx] = updated;
        } else {
          this.currentPlan.days.push(updated);
        }
        this.dayEditorOpen = false;
      } catch (e) {
        alert('Failed to save: ' + e.message);
      } finally {
        this.daySaving = false;
      }
    },

    // ── Meal editor ─────────────────────────────────────────
    openMealEditor(meal) {
      this.editingMeal = meal;
      this.mealForm = meal
        ? { ...meal }
        : { name: '', meal_type: 'home_cooked', notes: '', recipe_url: '', has_leftovers: false, easy_to_make: false, shared_ingredients: '' };
      this.mealEditorOpen = true;
    },

    async saveMeal() {
      if (!this.mealForm.name.trim()) return;
      this.mealSaving = true;
      try {
        if (this.editingMeal) {
          const updated = await this.api('PUT', `/meals/${this.editingMeal.id}`, this.mealForm);
          const idx = this.meals.findIndex(m => m.id === updated.id);
          if (idx >= 0) this.meals[idx] = updated;
        } else {
          const created = await this.api('POST', '/meals', this.mealForm);
          this.meals.push(created);
          this.meals.sort((a, b) => a.name.localeCompare(b.name));
        }
        this.mealEditorOpen = false;
      } catch (e) {
        alert('Failed to save: ' + e.message);
      } finally {
        this.mealSaving = false;
      }
    },

    async deleteMeal() {
      if (!this.editingMeal) return;
      if (!confirm(`Delete "${this.editingMeal.name}"? It will be removed from the library.`)) return;
      try {
        await this.api('DELETE', `/meals/${this.editingMeal.id}`);
        this.meals = this.meals.filter(m => m.id !== this.editingMeal.id);
        this.mealEditorOpen = false;
      } catch (e) {
        alert('Failed to delete: ' + e.message);
      }
    },

    // ── AI ───────────────────────────────────────────────────
    async generateAI() {
      if (!this.currentPlan) return;
      if (!this.aiConfigured) {
        this.activeTab = 'settings';
        return;
      }
      this.aiLoading = true;
      this.aiError = null;
      this.aiSuccess = false;
      try {
        const result = await this.api('POST', '/ai/generate', {
          week_start: this.currentPlan.week_start,
          existing_plan_id: this.currentPlan.id,
        });
        // reload the plan to get updated days with meal objects
        this.currentPlan = await this.api('GET', `/plans/${result.plan_id}`);
        this.aiSuccess = true;
        setTimeout(() => { this.aiSuccess = false; }, 5000);
      } catch (e) {
        this.aiError = e.message;
        // re-check status in case the key was removed
        await this.loadAIStatus();
      } finally {
        this.aiLoading = false;
      }
    },

    // ── History ─────────────────────────────────────────────
    browseWeeks() {
      this.activeTab = 'history';
    },

    async toggleHistoryPlan(planId) {
      if (this.expandedPlan === planId) {
        this.expandedPlan = null;
        return;
      }
      this.expandedPlan = planId;
      if (!this.historyDetails[planId]) {
        const detail = await this.api('GET', `/plans/${planId}`);
        this.historyDetails = { ...this.historyDetails, [planId]: detail };
      }
    },

    planStatusClass(status) {
      return {
        draft: 'bg-gray-100 text-gray-600',
        active: 'bg-green-100 text-green-700',
        complete: 'bg-blue-100 text-blue-700',
      }[status] || 'bg-gray-100 text-gray-600';
    },

    // ── Settings ─────────────────────────────────────────────
    toggleDay(field, idx) {
      const arr = [...this.settings[field]];
      const pos = arr.indexOf(idx);
      if (pos >= 0) arr.splice(pos, 1);
      else arr.push(idx);
      this.settings[field] = arr.sort((a, b) => a - b);
    },

    async saveSettings() {
      this.settingsSaving = true;
      this.settingsSaved = false;
      try {
        this.settings = await this.api('PUT', '/settings', {
          gym_days: this.settings.gym_days,
          eat_out_days: this.settings.eat_out_days,
        });
        this.settingsSaved = true;
        setTimeout(() => { this.settingsSaved = false; }, 3000);
      } catch (e) {
        alert('Failed to save settings: ' + e.message);
      } finally {
        this.settingsSaving = false;
      }
    },
  };
}
