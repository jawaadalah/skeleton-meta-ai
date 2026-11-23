package com.jawaadalah.ujilangsung

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(GameView(this))
    }

    private class GameView(context: android.content.Context) : View(context) {
        // Paints
        private val paintBackground = Paint().apply { color = Color.BLACK }
        private val paintPlayer = Paint().apply { color = Color.CYAN }
        private val paintEnemy = Paint().apply { color = Color.RED }
        private val paintText = Paint().apply {
            color = Color.WHITE
            textSize = 60f
            isAntiAlias = true
        }

        // Player properties
        private var playerX = 0f
        private var playerY = 0f
        private val playerRadius = 50f

        // Game state
        private var score = 0
        private var lives = 3
        private var gameOver = false

        // Timing
        private var lastSpawnTime = 0L
        private var startTime = 0L

        // Difficulty
        private var enemySpeed = 8f
        private var spawnInterval = 1500L // ms

        // Enemies
        private data class Enemy(var x: Float, var y: Float, val size: Float, var speed: Float)
        private val enemies = mutableListOf<Enemy>()

        init {
            // Initialize positions after view size is known
            post {
                playerX = (width / 2).toFloat()
                playerY = (height - 200).toFloat()
                startTime = System.currentTimeMillis()
                lastSpawnTime = startTime
            }
        }

        override fun onDraw(canvas: Canvas) {
            // Background
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paintBackground)

            // Draw player
            canvas.drawCircle(playerX, playerY, playerRadius, paintPlayer)

            // Draw enemies
            for (enemy in enemies) {
                canvas.drawRect(
                    enemy.x - enemy.size,
                    enemy.y - enemy.size,
                    enemy.x + enemy.size,
                    enemy.y + enemy.size,
                    paintEnemy
                )
            }

            // Draw HUD
            canvas.drawText("Score: $score", 30f, 80f, paintText)
            canvas.drawText("Lives: $lives", 30f, 150f, paintText)

            // Game Over overlay
            if (gameOver) {
                val msg = "Game Over! Tap to Restart"
                val textWidth = paintText.measureText(msg)
                canvas.drawText(msg, (width - textWidth) / 2, (height / 2).toFloat(), paintText)
            }

            // Update only if not game over
            if (!gameOver) {
                val now = System.currentTimeMillis()
                // Spawn enemies based on interval
                if (now - lastSpawnTime >= spawnInterval) {
                    spawnEnemy()
                    lastSpawnTime = now
                }

                // Move enemies
                val iterator = enemies.iterator()
                while (iterator.hasNext()) {
                    val enemy = iterator.next()
                    enemy.y += enemy.speed
                    // Remove off-screen
                    if (enemy.y - enemy.size > height) {
                        iterator.remove()
                        score += 1
                    } else {
                        // Collision detection
                        val dx = enemy.x - playerX
                        val dy = enemy.y - playerY
                        val distance = hypot(dx, dy)
                        if (distance < playerRadius + enemy.size) {
                            iterator.remove()
                            lives -= 1
                            if (lives <= 0) {
                                gameOver = true
                            }
                        }
                    }
                }

                // Difficulty scaling
                if (score > 0 && score % 10 == 0) {
                    // increase speed and spawn rate every 10 points
                    enemySpeed = min(30f, enemySpeed + 2f)
                    spawnInterval = max(400L, spawnInterval - 100L)
                }
            }

            // Loop
            postInvalidateDelayed(16)
        }

        private fun spawnEnemy() {
            val size = 40f
            val xPos = (size + (width - 2 * size) * Math.random()).toFloat()
            val enemy = Enemy(xPos, -size, size, enemySpeed)
            enemies.add(enemy)
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            if (event.action == MotionEvent.ACTION_DOWN) {
                if (gameOver) {
                    resetGame()
                } else {
                    // Move player horizontally to touch X, keep Y constant
                    playerX = event.x.coerceIn(playerRadius, width - playerRadius)
                }
                return true
            }
            if (event.action == MotionEvent.ACTION_MOVE && !gameOver) {
                playerX = event.x.coerceIn(playerRadius, width - playerRadius)
                return true
            }
            return super.onTouchEvent(event)
        }

        private fun resetGame() {
            score = 0
            lives = 3
            gameOver = false
            enemies.clear()
            enemySpeed = 8f
            spawnInterval = 1500L
            startTime = System.currentTimeMillis()
            lastSpawnTime = startTime
            playerX = (width / 2).toFloat()
            playerY = (height - 200).toFloat()
        }
    }
}