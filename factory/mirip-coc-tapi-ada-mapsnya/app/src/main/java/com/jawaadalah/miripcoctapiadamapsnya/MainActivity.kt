package com.jawaadalah.miripcoctapiadamapsnya

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val gameView = GameView(this)
        setContentView(gameView)
    }

    private class GameView(context: android.content.Context) : View(context) {

        // Paints
        private val paintBackground = Paint().apply { color = Color.DKGRAY }
        private val paintGrid = Paint().apply { color = Color.LTGRAY; strokeWidth = 2f }
        private val paintPlayer = Paint().apply { color = Color.YELLOW }
        private val paintEnemy = Paint().apply { color = Color.RED }
        private val paintText = Paint().apply { color = Color.WHITE; textSize = 48f }

        // Game state
        private var isPlaying = true
        private var score = 0
        private var lives = 3

        // Player
        private var playerX = 0f
        private var playerY = 0f
        private val playerRadius = 30f
        private var playerTargetX = 0f
        private var playerTargetY = 0f
        private var playerSpeed = 8f

        // Enemies
        private data class Enemy(var x: Float, var y: Float, var vx: Float, var vy: Float)
        private val enemies = mutableListOf<Enemy>()
        private var spawnCounter = 0
        private var spawnInterval = 60 // frames

        // Map
        private val mapRows = 12
        private val mapCols = 8
        private val cellSize = 100f
        private val obstacleGrid = Array(mapRows) { BooleanArray(mapCols) }

        // Frame tracking
        private var frameCount = 0

        init {
            // Initialize player position at center of first cell
            playerX = cellSize / 2f
            playerY = cellSize / 2f
            playerTargetX = playerX
            playerTargetY = playerY

            // Random obstacles (simple pattern)
            for (r in 0 until mapRows) {
                for (c in 0 until mapCols) {
                    // Create a border of obstacles
                    obstacleGrid[r][c] = (r == 0 || c == 0 || r == mapRows - 1 || c == mapCols - 1)
                }
            }
        }

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            drawBackground(canvas)
            drawMap(canvas)
            drawPlayer(canvas)
            drawEnemies(canvas)
            drawHUD(canvas)

            if (isPlaying) {
                updateGame()
            }

            // Loop at ~60 FPS
            postInvalidateDelayed(16)
        }

        private fun drawBackground(canvas: Canvas) {
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paintBackground)
        }

        private fun drawMap(canvas: Canvas) {
            // Draw grid
            for (r in 0..mapRows) {
                val y = r * cellSize
                canvas.drawLine(0f, y, mapCols * cellSize, y, paintGrid)
            }
            for (c in 0..mapCols) {
                val x = c * cellSize
                canvas.drawLine(x, 0f, x, mapRows * cellSize, paintGrid)
            }
            // Draw obstacles
            val obstaclePaint = Paint().apply { color = Color.GRAY }
            for (r in 0 until mapRows) {
                for (c in 0 until mapCols) {
                    if (obstacleGrid[r][c]) {
                        val left = c * cellSize
                        val top = r * cellSize
                        canvas.drawRect(left, top, left + cellSize, top + cellSize, obstaclePaint)
                    }
                }
            }
        }

        private fun drawPlayer(canvas: Canvas) {
            canvas.drawCircle(playerX, playerY, playerRadius, paintPlayer)
        }

        private fun drawEnemies(canvas: Canvas) {
            for (e in enemies) {
                canvas.drawRect(
                    e.x - playerRadius,
                    e.y - playerRadius,
                    e.x + playerRadius,
                    e.y + playerRadius,
                    paintEnemy
                )
            }
        }

        private fun drawHUD(canvas: Canvas) {
            canvas.drawText("Score: $score", 20f, 60f, paintText)
            canvas.drawText("Lives: $lives", 20f, 120f, paintText)
            if (!isPlaying) {
                val msg = "Game Over! Tap to Restart"
                val textWidth = paintText.measureText(msg)
                canvas.drawText(
                    msg,
                    (width - textWidth) / 2f,
                    (height / 2f),
                    paintText
                )
            }
        }

        private fun updateGame() {
            frameCount++

            // Update player movement towards target
            val dx = playerTargetX - playerX
            val dy = playerTargetY - playerY
            val dist = sqrt(dx * dx + dy * dy)
            if (dist > playerSpeed) {
                playerX += (dx / dist) * playerSpeed
                playerY += (dy / dist) * playerSpeed
            } else {
                playerX = playerTargetX
                playerY = playerTargetY
            }

            // Spawn enemies
            spawnCounter++
            if (spawnCounter >= spawnInterval) {
                spawnCounter = 0
                spawnEnemy()
            }

            // Update enemies
            val iterator = enemies.iterator()
            while (iterator.hasNext()) {
                val e = iterator.next()
                // Move towards player
                val ex = playerX - e.x
                val ey = playerY - e.y
                val edist = sqrt(ex * ex + ey * ey)
                val speed = 4f + (score / 2000f) // increase speed with score
                if (edist != 0f) {
                    e.vx = (ex / edist) * speed
                    e.vy = (ey / edist) * speed
                } else {
                    e.vx = 0f
                    e.vy = 0f
                }
                e.x += e.vx
                e.y += e.vy

                // Collision with player
                val collideDist = playerRadius * 2
                if (sqrt((e.x - playerX) * (e.x - playerX) + (e.y - playerY) * (e.y - playerY)) < collideDist) {
                    iterator.remove()
                    lives--
                    if (lives <= 0) {
                        isPlaying = false
                    }
                }
            }

            // Increment score
            score += 1
        }

        private fun spawnEnemy() {
            // Spawn at random edge cell that is not an obstacle
            var spawnX = 0f
            var spawnY = 0f
            val edge = (0..3).random()
            when (edge) {
                0 -> { // top
                    spawnX = (1 until mapCols - 1).random() * cellSize + cellSize / 2f
                    spawnY = cellSize / 2f
                }
                1 -> { // bottom
                    spawnX = (1 until mapCols - 1).random() * cellSize + cellSize / 2f
                    spawnY = (mapRows - 1) * cellSize + cellSize / 2f
                }
                2 -> { // left
                    spawnX = cellSize / 2f
                    spawnY = (1 until mapRows - 1).random() * cellSize + cellSize / 2f
                }
                3 -> { // right
                    spawnX = (mapCols - 1) * cellSize + cellSize / 2f
                    spawnY = (1 until mapRows - 1).random() * cellSize + cellSize / 2f
                }
            }
            enemies.add(Enemy(spawnX, spawnY, 0f, 0f))
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            if (event.action == MotionEvent.ACTION_DOWN) {
                if (isPlaying) {
                    // Move player to touched cell if not obstacle
                    val col = (event.x / cellSize).toInt()
                    val row = (event.y / cellSize).toInt()
                    if (row in 0 until mapRows && col in 0 until mapCols && !obstacleGrid[row][col]) {
                        playerTargetX = col * cellSize + cellSize / 2f
                        playerTargetY = row * cellSize + cellSize / 2f
                    }
                } else {
                    // Restart
                    resetGame()
                }
                return true
            }
            return super.onTouchEvent(event)
        }

        private fun resetGame() {
            isPlaying = true
            score = 0
            lives = 3
            enemies.clear()
            spawnCounter = 0
            frameCount = 0
            playerX = cellSize / 2f
            playerY = cellSize / 2f
            playerTargetX = playerX
            playerTargetY = playerY
        }
    }
}