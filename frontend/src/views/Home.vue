<template>
  <div>
    <!-- Hero -->
    <section class="hero-gradient min-h-[50vh] md:min-h-[60vh] flex items-center overflow-hidden">
      <div class="hero-deco" aria-hidden="true">
        <span style="top:15%;left:8%;width:8px;height:8px"></span>
        <span style="top:25%;right:15%"></span>
        <span style="top:60%;left:5%;width:10px;height:10px;opacity:0.08"></span>
        <span style="bottom:20%;right:8%"></span>
        <span style="top:40%;left:50%;width:4px;height:4px;opacity:0.06"></span>
      </div>
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 relative z-10">
        <div class="max-w-3xl">
          <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 text-amber-400 text-sm font-medium mb-6 border border-white/10">
            <span class="w-2 h-2 bg-amber-400 rounded-full animate-pulse-dot"></span>
            <span>For Indie Developers</span>
          </div>
          <h1 class="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-tight mb-2">
            No team? No problem.<br><span class="gradient-text">Just you, AI, and the vibe.</span>
          </h1>
          <p class="text-lg sm:text-xl text-amber-300/80 font-medium mb-3 max-w-2xl">
            Vibe first. Code second. Ship always.
          </p>
          <p class="text-base text-slate-500 mb-8 max-w-2xl">
            <em>Know What Works. Ship What Matters.</em>
          </p>
          <div class="flex flex-wrap gap-4">
            <router-link to="/aitools" class="btn btn-primary no-underline">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              Explore Tools
            </router-link>
            <router-link to="/blog" class="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg border border-white/20 text-white font-semibold text-sm no-underline hover:bg-white/10 transition-all">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
              Read Blog
            </router-link>
          </div>
        </div>
      </div>
    </section>



    <!-- Section divider -->
    <div class="section-divider" aria-hidden="true"></div>

    <!-- Blog -->
    <section class="py-20 bg-white dark:bg-slate-900 reveal">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-10">
          <h2 class="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">📝 Dev Experiences</h2>
          <p class="text-lg text-slate-600 dark:text-slate-400 mb-6">Personal stories, deployment diaries, tech stack breakdowns, and hard-won lessons from the trenches.</p>
          <div class="flex flex-wrap justify-center gap-2">
            <button v-for="c in blogCategories" :key="c"
              @click="activeCategory = (activeCategory === c ? '' : c)"
              class="filter-btn" :class="{ active: activeCategory === c }">
              {{ c }}
            </button>
          </div>
        </div>
        <div v-if="filteredPosts.length" class="divide-y divide-gray-100 dark:divide-slate-700">
          <a v-for="(p, i) in filteredPosts.slice(0,6)" :key="p.slug" :href="'/blog/' + p.slug"
             class="flex items-start gap-4 py-4 px-2 -mx-2 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors no-underline group" :style="{ transitionDelay: i * 50 + 'ms' }">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span v-if="p.category" class="text-xs px-2 py-0.5 rounded-full font-medium" style="background:var(--color-brand-lightest);color:var(--color-brand)">{{ p.category }}</span>
              </div>
              <h3 class="text-lg font-bold text-slate-900 dark:text-white group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors mb-1">{{ p.title }}</h3>
              <p class="text-sm text-slate-500 dark:text-slate-400 line-clamp-2">{{ p.excerpt }}</p>
            </div>
            <svg class="w-5 h-5 text-gray-300 dark:text-slate-600 flex-shrink-0 mt-1 group-hover:text-amber-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </a>
        </div>
        <div v-else class="divide-y divide-gray-100 dark:divide-slate-700">
          <div v-for="i in 3" :key="'ps'+i" class="flex items-start gap-4 py-4 px-2">
            <div class="flex-1 space-y-2">
              <div class="skeleton h-4 w-16"></div>
              <div class="skeleton h-5 w-3/4"></div>
              <div class="skeleton h-4 w-full"></div>
            </div>
          </div>
        </div>
        <div class="text-center mt-10"><a href="/blog/" class="btn btn-primary no-underline">All Posts →</a></div>
      </div>
    </section>

    <!-- Section divider -->
    <div class="section-divider" aria-hidden="true"></div>

    <!-- AI Tool Picks -->
    <section class="py-20 bg-slate-50 dark:bg-slate-800/50 reveal">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-end justify-between mb-12">
          <div>
            <h2 class="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-2">🤖 AI Tool Picks</h2>
            <p class="text-lg text-slate-600 dark:text-slate-400">Hand-picked tools for indie devs — AI coding agents, game engines, creative tools.</p>
          </div>
          <router-link to="/aitools" class="hidden sm:inline-flex items-center gap-1 text-sm font-semibold flex-shrink-0" style="color:var(--color-brand)">
            View All →
          </router-link>
        </div>
        <div v-if="aiTools.length" class="tool-grid">
          <a v-for="(t, i) in aiTools.slice(0,6)" :key="t.slug || t.name" :href="'/aitools/' + t.slug"
             class="tool-card no-underline block" :style="{ transitionDelay: i * 60 + 'ms' }">
            <IconDisplay :icon="t.icon" fallback="🔧" size="2rem" />
            <h3 class="text-lg font-bold text-slate-900 dark:text-white mb-2">{{ t.title }}</h3>
            <div class="flex flex-wrap gap-2 mb-2">
              <span class="text-xs px-2 py-0.5 rounded-full" style="background:var(--color-brand-lightest);color:var(--color-brand)">{{ t.category }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">{{ t.subtitle }}</span>
            </div>
            <p class="text-sm text-slate-600 dark:text-slate-400 line-clamp-2">{{ t.description }}</p>
          </a>
        </div>
        <div v-else class="tool-grid">
          <div v-for="i in 6" :key="'ts'+i" class="rounded-xl p-6"><div class="skeleton w-10 h-10 mb-3"></div><div class="skeleton h-5 w-3/4 mb-2"></div><div class="skeleton h-4 w-full"></div></div>
        </div>
        <div class="text-center mt-10 sm:hidden"><router-link to="/aitools" class="btn btn-primary no-underline">View All Tools →</router-link></div>
      </div>
    </section>

    <!-- Section divider -->
    <div class="section-divider" aria-hidden="true"></div>

    <!-- Featured Projects -->
    <section class="py-20 bg-white dark:bg-slate-900 reveal">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-end justify-between mb-12">
          <div>
            <h2 class="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-2">🚀 Featured Projects</h2>
            <p class="text-lg text-slate-600 dark:text-slate-400">Inspiring indie and vibe-coded projects from the community.</p>
          </div>
          <router-link to="/projects" class="hidden sm:inline-flex items-center gap-1 text-sm font-semibold flex-shrink-0" style="color:var(--color-brand)">
            View All →
          </router-link>
        </div>
        <div v-if="featuredProjects.length" class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div v-for="(p, i) in featuredProjects.slice(0,3)" :key="p.slug" class="tool-card no-underline block h-full flex flex-col"
               :style="{ transitionDelay: i * 80 + 'ms' }">
            <div class="flex items-start gap-3 mb-3">
              <IconDisplay :icon="p.icon" fallback="🚀" size="2rem" />
              <div class="min-w-0 flex-1">
                <h3 class="text-lg font-bold text-slate-900 dark:text-white">{{ p.title }}</h3>
                <span class="inline-block text-xs px-2 py-0.5 rounded-full mt-1"
                      :style="{ background: p.category === 'vibe-project' ? 'oklch(0.9 0.06 30 / 0.3)' : 'oklch(0.9 0.06 70 / 0.3)', color: p.category === 'vibe-project' ? 'var(--color-brand)' : 'oklch(0.55 0.15 60)' }">
                  {{ p.category === 'vibe-project' ? '🎧 Vibe Coding' : '💼 Indie Project' }}
                </span>
              </div>
            </div>
            <p class="text-sm text-slate-600 dark:text-slate-400 flex-1">{{ p.description }}</p>
            <div class="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700 flex items-center justify-between">
              <div class="flex flex-wrap gap-1.5">
                <span v-for="tech in (p.tech_stack || '').split(',').slice(0,3)" :key="tech"
                      class="text-xs px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                  {{ tech.trim() }}
                </span>
              </div>
              <a v-if="p.project_url" :href="p.project_url" target="_blank" rel="noopener"
                 class="text-xs font-semibold" style="color:var(--color-brand);text-decoration:none">
                {{ p.author || 'View' }} →
              </a>
            </div>
          </div>
        </div>
        <div v-else class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div v-for="i in 3" :key="'pf'+i" class="rounded-xl p-6">
            <div class="skeleton h-6 w-3/4 mb-4"></div>
            <div class="skeleton h-4 w-full mb-2"></div>
            <div class="skeleton h-4 w-4/5"></div>
          </div>
        </div>
        <div class="text-center mt-10 sm:hidden"><router-link to="/projects" class="btn btn-primary no-underline">View All Projects →</router-link></div>
      </div>
    </section>

    <!-- Section divider -->
    <div class="section-divider" aria-hidden="true"></div>

    <!-- Coming Soon -->
    <section class="py-20 bg-slate-50 dark:bg-slate-800/50 reveal">
      <div class="max-w-4xl mx-auto px-4 text-center">
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-6"
             style="background:var(--color-brand-lightest);color:var(--color-brand)">Coming Soon</div>
        <h2 class="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">🧠 AI-Powered Tools for Indie Devs</h2>
        <p class="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto mb-12">
          Interactive tools to help you ship faster, make better decisions, and stay focused on what matters.
        </p>
        <div class="grid md:grid-cols-3 gap-6 max-w-3xl mx-auto">
          <div class="rounded-xl p-6 border border-dashed" style="border-color:var(--color-brand-lightest)">
            <div class="text-3xl mb-3">🧭</div>
            <h3 class="font-bold text-slate-900 dark:text-white mb-1">Vibe Mentor</h3>
            <p class="text-xs text-slate-500">Describe your project idea — get a tech stack, roadmap, and estimated timeline.</p>
          </div>
          <div class="rounded-xl p-6 border border-dashed" style="border-color:var(--color-brand-lightest)">
            <div class="text-3xl mb-3">🔍</div>
            <h3 class="font-bold text-slate-900 dark:text-white mb-1">Market Scout</h3>
            <p class="text-xs text-slate-500">Analyze any niche — competition, demand, pricing, and growth potential.</p>
          </div>
          <div class="rounded-xl p-6 border border-dashed" style="border-color:var(--color-brand-lightest)">
            <div class="text-3xl mb-3">📊</div>
            <h3 class="font-bold text-slate-900 dark:text-white mb-1">Project Analyzer</h3>
            <p class="text-xs text-slate-500">Paste your project URL or describe your stack — get a health check and refactoring tips.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section divider -->
    <div class="section-divider" aria-hidden="true"></div>

    <!-- CTA -->
    <section class="py-20 cta-section reveal">
      <div class="max-w-4xl mx-auto px-4 text-center">
        <h2 class="text-3xl sm:text-4xl font-bold text-white mb-4">Know an Indie Dev Worth Featuring?</h2>
        <p class="text-white/70 text-lg mb-8">Got a recommendation, a question, or just want to share your own story? I'd love to hear from you.</p>
        <div class="flex flex-wrap justify-center gap-4">
          <a href="/contact" class="inline-block bg-white text-brand hover:bg-white/90 font-semibold px-8 py-3 rounded-lg text-base no-underline transition-all">Get in Touch</a>
          <a href="/about" class="inline-block border border-white/30 text-white hover:bg-white/10 font-semibold px-8 py-3 rounded-lg text-base no-underline transition-all">About This Site</a>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>

import { ref, computed, onMounted } from 'vue'
import IconDisplay from '../components/IconDisplay.vue'
import { usePageMeta, useJsonLd } from '../utils/meta.js'

const aiTools = ref([])
const posts = ref([])
const featuredProjects = ref([])
const activeCategory = ref('')

const blogCategories = computed(() => {
  const cats = new Set(posts.value.map(p => p.category).filter(Boolean))
  return [...cats].slice(0, 6)
})

const filteredPosts = computed(() => {
  if (!activeCategory.value) return posts.value
  return posts.value.filter(p => p.category === activeCategory.value)
})


onMounted(async () => {
  usePageMeta({
    title: '',
    description: 'Indie dev stories, curated AI tools, and developer spotlights. Build better, ship faster.',
    canonical: 'https://just4.tech/',
  })
  useJsonLd({
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Just4Tech',
    url: 'https://just4.tech/',
    description: 'Indie dev stories, curated tools, and developer spotlights.',
    potentialAction: {
      '@type': 'SearchAction',
      target: 'https://just4.tech/aitools?q={search_term_string}',
      'query-input': 'required name=search_term_string',
    },
  })

  const [toolsData, postsData, projectsData] = await Promise.allSettled([
    fetch('/api/software').then(r => r.ok ? r.json() : []),
    fetch('/api/posts').then(r => r.ok ? r.json() : []),
    fetch('/api/projects').then(r => r.ok ? r.json() : []),
  ])
  aiTools.value = toolsData.status === 'fulfilled' ? toolsData.value : []
  posts.value = postsData.status === 'fulfilled'
    ? postsData.value.filter(p => p.status === 'active')
    : []
  featuredProjects.value = projectsData.status === 'fulfilled'
    ? projectsData.value.slice(0, 3)
    : []
})
</script>
