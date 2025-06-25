/**
 * Optimistic Like/Unlike functionality for Latergram
 * This provides instant UI feedback without waiting for server responses
 */

// Function to show error toast notifications
function showErrorToast(message) {
  if (typeof showNotification === 'function') {
    showNotification(message, "danger");
  } else {
    // Fallback if showNotification is not available
    console.error(message);
    alert(message);
  }
}

// Initialize optimistic like functionality
function initOptimisticLikes() {
  document.querySelectorAll('.like-btn').forEach(button => {
    // Remove any existing event listeners to avoid duplicates
    const newButton = button.cloneNode(true);
    button.parentNode.replaceChild(newButton, button);
    
    newButton.addEventListener('click', function() {
      const postId = this.dataset.postId;
      const action = this.dataset.action;
      const btn = this;
      const likeCountSpan = btn.querySelector('.like-count');
      
      // Store original state for potential rollback
      const originalCount = parseInt(likeCountSpan.textContent);
      const originalClassName = btn.className;
      const originalAction = btn.dataset.action;
      const originalIcon = btn.querySelector('i').className;
      const originalStyle = btn.style.cssText;

      // Optimistic update - apply changes immediately
      let newCount;
      if (action === 'like') {
        newCount = originalCount + 1;
        btn.className = 'btn btn-danger btn-sm like-btn';
        btn.dataset.action = 'unlike';
        btn.querySelector('i').className = 'bi bi-heart-fill';
        // Apply styles for profile page compatibility
        if (btn.style.cssText !== '') {
          btn.style.cssText = 'background-color: #dc3545; border-color: #dc3545; color: white;';
        }
      } else {
        newCount = Math.max(0, originalCount - 1);
        btn.className = 'btn btn-outline-danger btn-sm like-btn';
        btn.dataset.action = 'like';
        btn.querySelector('i').className = 'bi bi-heart';
        // Apply styles for profile page compatibility
        if (btn.style.cssText !== '') {
          btn.style.cssText = 'background-color: transparent; border-color: #dc3545; color: #dc3545;';
        }
      }
      likeCountSpan.textContent = newCount;

      // Also update the hover overlay like count if it exists (profile page)
      const hoverLikeCount = document.getElementById(`hover-like-count-${postId}`);
      if (hoverLikeCount) {
        hoverLikeCount.textContent = newCount;
      }

      // Send request in background (no loading state)
      const url = action === 'like' ? `/api/like/${postId}` : `/api/unlike/${postId}`;

      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // Update with actual count from server if different
          if (data.new_count !== undefined && data.new_count !== newCount) {
            likeCountSpan.textContent = data.new_count;
            if (hoverLikeCount) {
              hoverLikeCount.textContent = data.new_count;
            }
          }
        } else {
          // Rollback optimistic update on error
          btn.className = originalClassName;
          btn.dataset.action = originalAction;
          btn.querySelector('i').className = originalIcon;
          btn.style.cssText = originalStyle;
          likeCountSpan.textContent = originalCount;
          if (hoverLikeCount) {
            hoverLikeCount.textContent = originalCount;
          }
          
          // Show error message (less intrusive than alert)
          console.error('Like error:', data.error);
          showErrorToast(data.error || 'Failed to update like');
        }
      })
      .catch(error => {
        // Rollback optimistic update on network error
        btn.className = originalClassName;
        btn.dataset.action = originalAction;
        btn.querySelector('i').className = originalIcon;
        btn.style.cssText = originalStyle;
        likeCountSpan.textContent = originalCount;
        if (hoverLikeCount) {
          hoverLikeCount.textContent = originalCount;
        }
        
        console.error('Network error:', error);
        showErrorToast('Network error occurred while updating like');
      });
    });
  });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initOptimisticLikes);

// Export for use in other scripts if needed
window.initOptimisticLikes = initOptimisticLikes;
