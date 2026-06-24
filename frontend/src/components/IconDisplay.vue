<template>
  <img v-if="isUrl" :src="proxyUrl" :alt="alt"
    :width="pxSize" :height="pxSize"
    :style="{ width: size, height: size }"
    class="rounded object-cover flex-shrink-0 inline-block align-middle"
    loading="lazy" decoding="async" :fetchpriority="fetchpriority"
    @error="onError">
  <span v-else :style="{ fontSize: size }">{{ fallback }}</span>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  icon: { type: String, default: '' },
  fallback: { type: String, default: '🤖' },
  alt: { type: String, default: '' },
  size: { type: String, default: '2rem' },
  fetchpriority: { type: String, default: 'auto' },
})

const failed = ref(false)

const isUrl = computed(() => {
  return !failed.value && props.icon && /^https?:\/\//.test(props.icon.trim())
})

const proxyUrl = computed(() => {
  if (!isUrl.value) return ''
  return `/api/icon-proxy?url=${encodeURIComponent(props.icon.trim())}`
})

const pxSize = computed(() => {
  const s = props.size
  if (s.endsWith('rem')) return Math.round(parseFloat(s) * 16)
  if (s.endsWith('px')) return parseInt(s, 10)
  if (s.endsWith('em')) return Math.round(parseFloat(s) * 16)
  return parseInt(s, 10) || 32
})

function onError() {
  failed.value = true
}
</script>
