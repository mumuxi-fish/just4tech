<template>
  <div>
    <section class="hero-gradient py-20">
      <div class="max-w-4xl mx-auto px-4 text-center relative z-10">
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 text-amber-400 text-sm font-medium mb-6 border border-white/10">
          <span class="w-2 h-2 bg-amber-400 rounded-full animate-pulse-dot"></span>
          <span>Blog &amp; Tutorials</span>
        </div>
        <h1 class="text-4xl sm:text-5xl font-bold text-white mb-4">Blog</h1>
        <p class="text-lg text-gray-400 max-w-2xl mx-auto">Indie dev diaries, vibe coding tips, tutorials, and tool reviews — written by a solo dev for solo devs.</p>
      </div>
    </section>

    <section class="py-16 bg-white dark:bg-slate-900">
      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Category Filters -->
        <div class="flex flex-wrap gap-3 mb-10 justify-center">
          <button
            v-for="cat in categories"
            :key="cat"
            @click="activeCategory = cat"
            :class="['filter-btn', { active: activeCategory === cat }]"
          >
            {{ cat }}
          </button>
        </div>

        <!-- Blog Posts List -->
        <div v-if="filteredPosts.length" class="divide-y divide-gray-100 dark:divide-slate-700">
          <router-link
            v-for="post in filteredPosts"
            :key="post.slug"
            :to="'/blog/' + post.slug"
            class="flex items-start gap-4 py-5 px-2 -mx-2 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors no-underline group"
          >
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span v-if="post.category" class="text-xs px-2 py-0.5 rounded-full font-medium" :class="categoryClass(post.category)">{{ post.category }}</span>
                <span class="text-xs text-gray-400 dark:text-slate-500">{{ post.date || '' }}</span>
              </div>
              <h3 class="text-lg font-bold text-gray-900 dark:text-white group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors mb-1">{{ post.title }}</h3>
              <p class="text-sm text-gray-500 dark:text-slate-400 line-clamp-2">{{ post.excerpt }}</p>
            </div>
            <svg class="w-5 h-5 text-gray-300 dark:text-slate-600 flex-shrink-0 mt-1 group-hover:text-amber-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </router-link>
        </div>
        <div v-else-if="loaded" class="text-center py-12">
          <p class="text-gray-500">No posts found in this category.</p>
        </div>
        <div v-else class="divide-y divide-gray-100 dark:divide-slate-700">
          <div v-for="i in 6" :key="'bl'+i" class="flex items-start gap-4 py-5 px-2">
            <div class="flex-1 space-y-2">
              <div class="flex gap-2"><div class="skeleton h-4 w-16"></div><div class="skeleton h-4 w-12"></div></div>
              <div class="skeleton h-5 w-3/4"></div>
              <div class="skeleton h-4 w-full"></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>


import { ref, computed, onMounted } from 'vue'
import { usePageMeta, useJsonLd } from '../utils/meta.js'

import { get } from '../api/index.js'

const posts = ref([])
const activeCategory = ref('All')
const loaded = ref(false)

const ALL_CATEGORIES = ['Tutorial', 'Vibe Coding', 'Indie Diary', 'Dev Tools', 'AI Tool', 'Project', 'Indie Dev', 'Site']

const categories = computed(() => {
  const fromData = new Set(posts.value.map(p => p.category).filter(Boolean))
  ALL_CATEGORIES.forEach(c => fromData.add(c))
  return ['All', ...[...fromData].sort()]
})

const filteredPosts = computed(() => {
  if (activeCategory.value === 'All') return posts.value
  return posts.value.filter(p => p.category === activeCategory.value)
})

onMounted(async () => {
  usePageMeta({
    title: 'Blog',
    description: 'Indie dev experiences, tutorials, and tool reviews.',
    canonical: 'https://just4.tech/blog',
  })
  useJsonLd({
    '@context': 'https://schema.org',
    '@type': 'Blog',
    name: 'Just4Tech Blog',
    url: 'https://just4.tech/blog',
    description: 'Indie dev experiences, tutorials, and tool reviews.',
    about: 'Indie development, AI tools, and shipping solo',
    publisher: {
      '@type': 'Organization',
      name: 'Just4Tech',
      url: 'https://just4.tech/',
    },
  })

  try {
    const data = await get('/api/posts')
    posts.value = (data || []).filter(p => p.status === 'active')
  } catch {
    posts.value = []
  }
  loaded.value = true
})

function categoryClass(cat) {
  const map = {
    'Tutorial': 'bg-blue-100 text-blue-700',
    'Vibe Coding': 'bg-purple-100 text-purple-700',
    'Indie Diary': 'bg-orange-100 text-orange-700',
    'Dev Tools': 'bg-sky-100 text-sky-700',
    'AI Tool': 'bg-amber-100 text-amber-700',
    'Project': 'bg-emerald-100 text-emerald-700',
    'Indie Dev': 'bg-rose-100 text-rose-700',
    'Site': 'bg-teal-100 text-teal-700',
  }
  return map[cat] || 'bg-slate-100 text-slate-700'
}
</script>
