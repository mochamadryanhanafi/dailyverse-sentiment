<script>
  import { onMount, tick } from "svelte";
  import { api } from "../lib/api/client.js";

  let isOpen = false;
  let isThinking = false;
  let message = "";
  let chatHistory = []; // { role: 'user' | 'ai', content: string }
  let chatContainer;

  // Scroll to bottom whenever chatHistory changes
  async function scrollToBottom() {
    await tick();
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  function toggleChat() {
    isOpen = !isOpen;
    if (isOpen && chatHistory.length === 0) {
      chatHistory = [
        { role: 'ai', content: 'Halo! Saya NanaAI, asisten analis untuk proyek DailyVerse Sentiment. Ada yang ingin Anda ketahui tentang statistik atau data terbaru kita?' }
      ];
    }
    scrollToBottom();
  }

  async function sendMessage() {
    if (!message.trim() || isThinking) return;

    const userMessage = message.trim();
    chatHistory = [...chatHistory, { role: 'user', content: userMessage }];
    message = "";
    isThinking = true;
    scrollToBottom();

    // Add empty AI message to be streamed into
    chatHistory = [...chatHistory, { role: 'ai', content: '' }];
    try {
      const messagesToSend = chatHistory.slice(0, -1).map(msg => ({
        role: msg.role === 'ai' ? 'assistant' : 'user',
        content: msg.content
      }));
      const eventSource = api.chatbot.chatStream(messagesToSend);
      eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.event === 'chunk') {
          chatHistory[chatHistory.length - 1].content += data.text;
          scrollToBottom();
        } else if (data.event === 'error') {
          chatHistory[chatHistory.length - 1].content += `\n\n[Error: ${data.detail}]`;
          isThinking = false;
          eventSource.close();
          scrollToBottom();
        } else if (data.event === 'done') {
          isThinking = false;
          eventSource.close();
        }
      };

      eventSource.onerror = (err) => {
        const errorMsg = err && err.message ? err.message : "Tidak diketahui";
        chatHistory[chatHistory.length - 1].content += `\n\n[Koneksi terputus dari server AI: ${errorMsg}]`;
        isThinking = false;
        eventSource.close();
        scrollToBottom();
      };
    } catch (error) {
      chatHistory[chatHistory.length - 1].content += `\n\n[Error: ${error.message}]`;
      isThinking = false;
      scrollToBottom();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
</script>

<!-- Floating Action Button -->
<button
  class="fixed bottom-6 right-6 p-4 rounded-full bg-brand-600 text-white shadow-lg hover:bg-brand-700 transition-transform hover:scale-105 z-50 flex items-center justify-center"
  on:click={toggleChat}
  aria-label="Tanya Asisten AI"
>
  {#if isOpen}
    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
  {:else}
    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
  {/if}
</button>

<!-- Chat Window -->
{#if isOpen}
  <div class="fixed bottom-24 right-6 w-[350px] sm:w-[400px] h-[500px] max-h-[70vh] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden z-50 animate-fade-in">
    <!-- Header -->
    <div class="bg-brand-600 text-white p-4 flex justify-between items-center">
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
        <div class="text-left">
          <h3 class="font-bold">NanaAI</h3>
          <p class="text-xs opacity-90">Tanya saya tentang data analisis ini!</p>
        </div>
      </div>
    </div>

    <!-- Messages Area -->
    <div 
      bind:this={chatContainer}
      class="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50 dark:bg-slate-900/50"
    >
      {#each chatHistory as msg}
        <div class="flex {msg.role === 'user' ? 'justify-end' : 'justify-start'}">
          <div class="max-w-[85%] rounded-2xl px-4 py-2 {msg.role === 'user' ? 'bg-brand-600 text-white rounded-tr-sm' : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-tl-sm'} shadow-sm whitespace-pre-wrap text-sm">
            {msg.content}
            {#if msg.role === 'ai' && isThinking && msg === chatHistory[chatHistory.length - 1]}
              <span class="inline-block w-2 h-4 ml-1 bg-brand-500 animate-pulse align-middle"></span>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    <!-- Input Area -->
    <div class="p-3 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex gap-2 items-end">
      <textarea
        class="flex-1 max-h-32 min-h-[40px] resize-none border border-slate-300 dark:border-slate-700 rounded-xl px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 dark:bg-slate-800 dark:text-white"
        placeholder="Tanya sesuatu tentang data..."
        bind:value={message}
        on:keydown={handleKeydown}
        disabled={isThinking}
        rows="1"
      ></textarea>
      <button
        class="p-2 rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors h-[40px] w-[40px] flex items-center justify-center shrink-0"
        on:click={sendMessage}
        disabled={!message.trim() || isThinking}
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
      </button>
    </div>
  </div>
{/if}
